from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from sqlalchemy.orm import Session

from src.config import Settings
from src.services.doc_chunk.import_service import import_workspace_for_knowledge_entry
from src.services.doc_chunk.pipeline_runner import run_doc_chunk_pipeline
from src.services.doc_chunk.workspace_manager import cleanup_workspace, ensure_workspace, workspace_path_for_task
from src.db.session import SessionLocal
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FilePurpose, FileType, FileImportStatus
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_audit_log import TemplateAuditAction, TemplateAuditLog
from src.models.template_chapter import TemplateChapter
from src.models.template_parse_suggestion import TemplateParseSuggestion
from src.models.template_structure_diff import (
    TemplateStructureDiff,
    TemplateStructureDiffStatus,
)
from src.models.template_parse_task import (
    TemplateParseTask,
    TemplateParseTaskStatus,
    TemplateParseStrategy,
)
from src.models.template_parse_suggestion import TemplateSuggestionSource
from src.services.chunk_classification_service import classify_chunk
from src.services.classification_rule_index import load_classification_index
from src.services.docx_content_extractor import extract_fixed_paragraph_materials
from src.services.docx_outline_parser import parse_outline
from src.services.knowledge_chunk import build_knowledge_chunks, merge_classifications_into_suggestion


class TemplateParseServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append_log(task: TemplateParseTask, message: str, *, level: str = "info") -> None:
    lines = list(task.log_lines or [])
    lines.append({"ts": _now().isoformat(), "level": level, "message": message})
    task.log_lines = lines


def _resolve_docx_path(file_import: FileImport) -> Path:
    from src.services.docm_converter import ensure_docx_for_parse

    source = Path(Settings().storage_root) / file_import.storage_path
    if source.suffix.lower() == ".docm":
        return ensure_docx_for_parse(source)
    return source


def _pick_template_type(file_import: FileImport) -> TemplateType:
    if file_import.file_purpose == FilePurpose.qualification:
        return TemplateType.qualification
    return TemplateType.technical_bid


def _build_candidate_suggestions(materials: list[dict]) -> list[dict]:
    candidates: list[dict] = []
    for material in materials:
        content = str(material.get("content") or "")
        if not bool(material.get("extract_as_candidate")) and len(content) < 200:
            continue
        candidates.append(
            {
                "temp_id": f"c_{material['temp_id']}",
                "chapter_temp_id": material.get("chapter_temp_id"),
                "candidate_type": "ku",
                "title": material.get("title") or f"候选 {material['temp_id']}",
                "content_preview": content[:2000],
                "accepted": True,
            }
        )
    return candidates


def _classify_chunks_for_task(
    db: Session,
    *,
    kb_id,
    chunks,
    task: TemplateParseTask,
) -> dict:
    index = load_classification_index(db, kb_id=kb_id)
    llm_progress = {
        "total_chunks": len(chunks),
        "completed_chunks": 0,
        "failed_chunks": 0,
        "degraded_to_rule": 0,
        "batch_size": 1,
    }
    results = {}
    for chunk in chunks:
        result, degraded = classify_chunk(db, kb_id=kb_id, chunk=chunk, index=index)
        results[chunk.chunk_ref] = result
        llm_progress["completed_chunks"] += 1
        if degraded:
            llm_progress["degraded_to_rule"] += 1
        task.llm_progress = dict(llm_progress)
        db.flush()
    return results


def _to_suggested_tree(outline_nodes) -> list[dict]:
    return [
        {
            "temp_id": node.temp_id,
            "parent_temp_id": node.parent_temp_id,
            "title": node.title,
            "level": node.level,
            "sort_order": node.sort_order,
            "chapter_taxonomy_id": None,
            "product_category_ids": [],
            "required": True,
            "is_fixed_section": True,
            "ignored": False,
            "needs_manual_review": node.needs_manual_review,
        }
        for node in outline_nodes
    ]


def _build_structure_diff_payload(
    *,
    existing_chapters,
    suggested_tree: list[dict],
) -> dict:
    existing_map = {
        (row.parse_source_ref or str(row.template_chapter_id)): {
            "title": row.title,
            "level": row.level,
            "parent_id": str(row.parent_id) if row.parent_id else None,
            "sort_order": row.sort_order,
        }
        for row in existing_chapters
    }
    suggested_map = {
        str(item.get("temp_id")): {
            "title": str(item.get("title", "")),
            "level": int(item.get("level", 1) or 1),
            "parent_temp_id": str(item.get("parent_temp_id")) if item.get("parent_temp_id") else None,
            "sort_order": int(item.get("sort_order", 0) or 0),
        }
        for item in suggested_tree
    }
    added = [key for key in suggested_map if key not in existing_map]
    removed = [key for key in existing_map if key not in suggested_map]
    changed = []
    for key in suggested_map.keys() & existing_map.keys():
        old_item = existing_map[key]
        new_item = suggested_map[key]
        if (
            old_item["title"] != new_item["title"]
            or old_item["level"] != new_item["level"]
            or old_item["sort_order"] != new_item["sort_order"]
        ):
            changed.append(
                {
                    "temp_id": key,
                    "old": old_item,
                    "new": new_item,
                }
            )
    return {
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
        "added_temp_ids": added,
        "removed_temp_ids": removed,
        "changed_nodes": changed,
        "suggested_tree": suggested_tree,
    }


def _get_or_create_parse_task(
    db: Session,
    *,
    entry: DownstreamTaskEntry,
    file_import: FileImport,
) -> TemplateParseTask:
    payload = dict(entry.payload or {})
    parse_task_id = payload.get("parse_task_id")
    task: TemplateParseTask | None = None
    if parse_task_id:
        try:
            task = db.get(TemplateParseTask, uuid.UUID(str(parse_task_id)))
        except (TypeError, ValueError):
            task = None
    if task is None:
        task = TemplateParseTask(
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            downstream_entry_id=entry.entry_id,
            status=TemplateParseTaskStatus.pending,
            trace_id=uuid.uuid4(),
        )
        db.add(task)
        db.flush()
        payload["parse_task_id"] = str(task.parse_task_id)
        entry.payload = payload
    elif task.downstream_entry_id is None:
        task.downstream_entry_id = entry.entry_id
    return task


def enqueue_template_parse(
    db: Session,
    *,
    kb_id: uuid.UUID,
    import_id: uuid.UUID,
    operator_id: str,
    trace_id: uuid.UUID | None,
    force_reparse: bool = False,
) -> TemplateParseTask:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise TemplateParseServiceError("File import not found", code="NOT_FOUND", status_code=404)
    if record.status != FileImportStatus.confirmed or record.file_purpose != FilePurpose.template_file:
        raise TemplateParseServiceError(
            "Import must be confirmed template_file",
            code="INVALID_STATE",
            status_code=422,
        )

    running = (
        db.query(TemplateParseTask)
        .filter(
            TemplateParseTask.kb_id == kb_id,
            TemplateParseTask.import_id == import_id,
            TemplateParseTask.status.in_(
                [TemplateParseTaskStatus.pending, TemplateParseTaskStatus.running]
            ),
        )
        .first()
    )
    if running and not force_reparse:
        raise TemplateParseServiceError(
            "Parse task is already in progress",
            code="PARSE_IN_PROGRESS",
            status_code=409,
        )

    task = TemplateParseTask(
        kb_id=kb_id,
        import_id=import_id,
        status=TemplateParseTaskStatus.pending,
        trace_id=trace_id or uuid.uuid4(),
    )
    db.add(task)
    db.flush()

    pending_entry = (
        db.query(DownstreamTaskEntry)
        .filter(
            DownstreamTaskEntry.kb_id == kb_id,
            DownstreamTaskEntry.import_id == import_id,
            DownstreamTaskEntry.task_type == DownstreamTaskType.template_file_parse,
            DownstreamTaskEntry.status == DownstreamTaskStatus.pending,
        )
        .order_by(DownstreamTaskEntry.created_at.asc())
        .first()
    )
    if pending_entry is None:
        pending_entry = DownstreamTaskEntry(
            kb_id=kb_id,
            import_id=import_id,
            task_type=DownstreamTaskType.template_file_parse,
            status=DownstreamTaskStatus.pending,
            payload={},
        )
        db.add(pending_entry)
        db.flush()

    payload = dict(pending_entry.payload or {})
    payload["parse_task_id"] = str(task.parse_task_id)
    payload["enqueued_by"] = operator_id
    pending_entry.payload = payload
    db.commit()
    db.refresh(task)
    return task


def _import_knowledge_entry_document(
    db: Session,
    *,
    file_import: FileImport,
    task: TemplateParseTask,
) -> None:
    if not Settings().use_doc_chunk_parse:
        return
    if file_import.file_purpose != FilePurpose.template_file:
        return

    docx_path = _resolve_docx_path(file_import)
    storage_root = Path(Settings().storage_root)
    workspace = workspace_path_for_task(
        storage_root=storage_root,
        kb_id=file_import.kb_id,
        import_id=file_import.import_id,
        parse_task_id=task.parse_task_id,
    )
    ensure_workspace(workspace, overwrite=True)
    try:
        run_doc_chunk_pipeline(docx_path, workspace)
        try:
            with db.begin_nested():
                result = import_workspace_for_knowledge_entry(
                    db,
                    kb_id=file_import.kb_id,
                    import_id=file_import.import_id,
                    workspace=workspace,
                    file_import=file_import,
                    persist_outline=False,
                    persist_candidates=False,
                )
            _append_log(
                task,
                (
                    f"知识录入文档已就绪：document_id={result.document_id} "
                    f"tree_nodes={result.tree_node_count}"
                ),
            )
            db.flush()
        except Exception as exc:
            _append_log(
                task,
                f"知识录入文档导入失败（不影响模板解析）: {exc}",
                level="warning",
            )
    finally:
        cleanup_workspace(workspace, on_success=True)


def _run_entry(db: Session, entry: DownstreamTaskEntry) -> None:
    file_import = db.get(FileImport, entry.import_id)
    if file_import is None:
        entry.status = DownstreamTaskStatus.failed
        db.commit()
        return

    task = _get_or_create_parse_task(db, entry=entry, file_import=file_import)
    task.status = TemplateParseTaskStatus.running
    task.parse_strategy = TemplateParseStrategy.docx
    task.started_at = _now()
    task.error_message = None
    _append_log(task, "开始解析模板文件")
    db.add(
        TemplateAuditLog(
            trace_id=task.trace_id,
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            template_id=task.template_id,
            operator_id="system",
            action=TemplateAuditAction.parse_start,
            payload_summary={"parse_task_id": str(task.parse_task_id)},
        )
    )
    db.flush()

    try:
        if file_import.file_type != FileType.docx:
            raise ValueError("Only docx is supported in P1")

        docx_path = _resolve_docx_path(file_import)
        if not docx_path.exists():
            raise FileNotFoundError(f"File not found: {docx_path}")

        _import_knowledge_entry_document(db, file_import=file_import, task=task)

        outline_nodes = parse_outline(docx_path)
        materials = extract_fixed_paragraph_materials(docx_path, outline_nodes=outline_nodes)
        suggested_candidates = _build_candidate_suggestions(materials)
        suggested_tree = _to_suggested_tree(outline_nodes)
        chunks = build_knowledge_chunks(
            outline_nodes=outline_nodes,
            materials=materials,
            candidates=suggested_candidates,
        )
        classification_results = _classify_chunks_for_task(
            db,
            kb_id=file_import.kb_id,
            chunks=chunks,
            task=task,
        )
        merged = merge_classifications_into_suggestion(
            suggested_chapter_tree=suggested_tree,
            suggested_materials=materials,
            suggested_candidates=suggested_candidates,
            chunks=chunks,
            results=classification_results,
        )
        suggested_tree = merged["suggested_chapter_tree"]
        materials = merged["suggested_materials"]
        suggested_candidates = merged["suggested_candidates"]

        template = (
            db.query(Template)
            .filter(
                Template.kb_id == file_import.kb_id,
                Template.source_import_id == file_import.import_id,
            )
            .order_by(Template.created_at.desc())
            .first()
        )
        if template is None:
            template = Template(
                kb_id=file_import.kb_id,
                source_import_id=file_import.import_id,
                template_name=file_import.file_name,
                template_type=_pick_template_type(file_import),
                product_category_ids=file_import.product_category_ids or [],
                status=TemplateStatus.draft,
                confirmed=False,
                created_by=file_import.confirmed_by or file_import.created_by or "system",
            )
            db.add(template)
            db.flush()
        is_structure_locked = bool(template.confirmed and template.structure_locked_at)

        suggestion = (
            db.query(TemplateParseSuggestion)
            .filter(TemplateParseSuggestion.parse_task_id == task.parse_task_id)
            .one_or_none()
        )
        if suggestion is None:
            suggestion = TemplateParseSuggestion(
                parse_task_id=task.parse_task_id,
                kb_id=file_import.kb_id,
            )
            db.add(suggestion)

        suggestion.suggested_library_name = None
        suggestion.suggested_product_category_ids = []
        suggestion.suggested_chapter_tree = suggested_tree
        suggestion.suggested_materials = materials
        suggestion.suggested_candidates = suggested_candidates
        suggestion.suggestion_source = TemplateSuggestionSource(merged["suggestion_source"])
        suggestion.rationale = "docx structure parse + chunk classification"

        task.template_id = template.template_id
        if is_structure_locked:
            existing_chapters = (
                db.query(TemplateChapter)
                .filter(TemplateChapter.template_id == template.template_id)
                .all()
            )
            diff_payload = _build_structure_diff_payload(
                existing_chapters=existing_chapters,
                suggested_tree=suggested_tree,
            )
            diff = (
                db.query(TemplateStructureDiff)
                .filter(
                    TemplateStructureDiff.parse_task_id == task.parse_task_id,
                    TemplateStructureDiff.template_id == template.template_id,
                )
                .one_or_none()
            )
            if diff is None:
                diff = TemplateStructureDiff(
                    kb_id=file_import.kb_id,
                    template_id=template.template_id,
                    parse_task_id=task.parse_task_id,
                )
                db.add(diff)
            diff.diff_payload = diff_payload
            diff.status = TemplateStructureDiffStatus.pending_review
            _append_log(task, "检测到已锁定模板，生成结构差异待人工审核")

        task.status = TemplateParseTaskStatus.parse_ready
        task.finished_at = _now()
        progress = task.llm_progress or {}
        _append_log(
            task,
            f"块级分类 {progress.get('completed_chunks', 0)}/{progress.get('total_chunks', 0)} 完成",
        )
        _append_log(task, "模板解析完成")

        entry.status = DownstreamTaskStatus.completed
        db.add(
            TemplateAuditLog(
                trace_id=task.trace_id,
                kb_id=file_import.kb_id,
                import_id=file_import.import_id,
                template_id=template.template_id,
                operator_id="system",
                action=TemplateAuditAction.parse_complete,
                payload_summary={
                    "parse_task_id": str(task.parse_task_id),
                    "downstream_entry_id": str(entry.entry_id),
                },
            )
        )
        db.commit()
    except Exception as exc:
        task.status = TemplateParseTaskStatus.failed
        task.error_message = str(exc)
        task.finished_at = _now()
        _append_log(task, f"模板解析失败: {exc}", level="error")
        entry.status = DownstreamTaskStatus.failed
        db.add(
            TemplateAuditLog(
                trace_id=task.trace_id,
                kb_id=file_import.kb_id,
                import_id=file_import.import_id,
                template_id=task.template_id,
                operator_id="system",
                action=TemplateAuditAction.parse_fail,
                payload_summary={
                    "parse_task_id": str(task.parse_task_id),
                    "error": str(exc),
                },
            )
        )
        db.commit()


def run_template_parse_once(db: Session) -> bool:
    entry = (
        db.query(DownstreamTaskEntry)
        .filter(
            DownstreamTaskEntry.task_type == DownstreamTaskType.template_file_parse,
            DownstreamTaskEntry.status == DownstreamTaskStatus.pending,
        )
        .order_by(DownstreamTaskEntry.created_at.asc())
        .first()
    )
    if entry is None:
        return False

    entry.status = DownstreamTaskStatus.claimed
    entry.claimed_by = "template_parse_runner"
    entry.claimed_at = _now()
    db.flush()
    _run_entry(db, entry)
    return True


def run_template_parse_pending(db: Session) -> None:
    while run_template_parse_once(db):
        pass


def run_template_parse_in_new_session() -> None:
    try:
        db = SessionLocal()
    except Exception:
        return
    try:
        run_template_parse_pending(db)
    except Exception:
        db.rollback()
    finally:
        db.close()
