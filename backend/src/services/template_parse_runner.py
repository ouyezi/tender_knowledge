from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from sqlalchemy.orm import Session

from src.config import Settings
from src.db.session import SessionLocal
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FilePurpose, FileType, FileImportStatus
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_audit_log import TemplateAuditAction, TemplateAuditLog
from src.models.template_parse_suggestion import TemplateParseSuggestion
from src.models.template_parse_task import (
    TemplateParseTask,
    TemplateParseTaskStatus,
    TemplateParseStrategy,
)
from src.services.docx_content_extractor import extract_fixed_paragraph_materials
from src.services.docx_outline_parser import parse_outline


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
    return Path(Settings().storage_root) / file_import.storage_path


def _pick_template_type(file_import: FileImport) -> TemplateType:
    if file_import.file_purpose == FilePurpose.qualification:
        return TemplateType.qualification
    return TemplateType.technical_bid


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

        outline_nodes = parse_outline(docx_path)
        materials = extract_fixed_paragraph_materials(docx_path, outline_nodes=outline_nodes)
        suggested_tree = _to_suggested_tree(outline_nodes)

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
        suggestion.suggested_product_category_ids = file_import.product_category_ids or []
        suggestion.suggested_chapter_tree = suggested_tree
        suggestion.suggested_materials = materials
        suggestion.suggested_candidates = []
        suggestion.rationale = "docx heading parse"

        task.template_id = template.template_id
        task.status = TemplateParseTaskStatus.parse_ready
        task.finished_at = _now()
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
