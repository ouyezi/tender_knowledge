from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
import uuid

from sqlalchemy.orm import Session

from src.config import Settings
from src.db.session import SessionLocal
from src.models.actual_bid_parse_task import (
    ActualBidParseStrategy,
    ActualBidParseTask,
    ActualBidParseTaskPhase,
    ActualBidParseTaskStatus,
)
from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_media_asset import DocumentMediaAsset
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services import bid_outline_diff_service, bid_outline_extract_service, candidate_generate_service
from src.services.docm_converter import ensure_docx_for_parse
from src.services.docx_document_walker import walk_document
from src.services.docx_image_extractor import extract_docx_images
from src.services.docx_toc_extractor import TocExtractResult, extract_toc_entries
from src.services.outline_heading_filter import filter_outline_entries
from src.services.outline_quality_service import sample_excluded_decisions, summarize_outline_quality
from src.services.text_sanitize import sanitize_pg_text

logger = logging.getLogger(__name__)

_PROGRESS_LOG_LIMIT = 200
_WALK_PROGRESS_INTERVAL = 200
_PERSIST_PROGRESS_INTERVAL = 500
_MAX_WALK_NODES = 500_000


class ActualBidParseServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _elapsed_ms(started_at: datetime | None, finished_at: datetime | None) -> int:
    started = _as_utc(started_at)
    finished = _as_utc(finished_at)
    if started is None or finished is None:
        return 0
    return int((finished - started).total_seconds() * 1000)


def _init_progress(*, file_size_bytes: int) -> dict:
    return {
        "phase": ActualBidParseTaskPhase.document_parse.value,
        "file_size_bytes": file_size_bytes,
        "total_nodes": 0,
        "processed_nodes": 0,
        "candidate_count": 0,
        "phase_timings_ms": {},
        "logs": [],
    }


def _persist_task_progress(
    task_id: uuid.UUID,
    *,
    db: Session | None = None,
    message: str | None = None,
    level: str = "info",
    task_phase: ActualBidParseTaskPhase | None = None,
    status: ActualBidParseTaskStatus | None = None,
    llm_progress: dict | None = None,
    **progress_updates,
) -> None:
    """Persist progress; uses caller session when provided, else a separate committed session."""

    def _apply(task: ActualBidParseTask) -> None:
        if status is not None:
            task.status = status
        if task_phase is not None:
            task.task_phase = task_phase
        progress = dict(
            llm_progress if llm_progress is not None else (task.llm_progress or _init_progress(file_size_bytes=0))
        )
        if message:
            logs = list(progress.get("logs") or [])
            logs.append({"ts": _now().isoformat(), "level": level, "message": message})
            progress["logs"] = logs[-_PROGRESS_LOG_LIMIT:]
            logger.info("actual_bid_parse task=%s %s", task_id, message)
        progress.update(progress_updates)
        task.llm_progress = progress

    if db is not None:
        task = db.get(ActualBidParseTask, task_id)
        if task is None:
            return
        _apply(task)
        db.flush()
        return

    with SessionLocal() as progress_db:
        task = progress_db.get(ActualBidParseTask, task_id)
        if task is None:
            return
        _apply(task)
        progress_db.commit()


def _load_progress(task_id: uuid.UUID, db: Session | None = None) -> dict:
    if db is not None:
        task = db.get(ActualBidParseTask, task_id)
        if task is None:
            return _init_progress(file_size_bytes=0)
        return dict(task.llm_progress or _init_progress(file_size_bytes=0))

    with SessionLocal() as progress_db:
        task = progress_db.get(ActualBidParseTask, task_id)
        if task is None:
            return _init_progress(file_size_bytes=0)
        return dict(task.llm_progress or _init_progress(file_size_bytes=0))


def _append_parse_log(
    task: ActualBidParseTask,
    db: Session,
    message: str,
    *,
    level: str = "info",
    **progress_updates,
) -> None:
    progress = _load_progress(task.parse_task_id, db)
    logs = list(progress.get("logs") or [])
    logs.append({"ts": _now().isoformat(), "level": level, "message": message})
    progress["logs"] = logs[-_PROGRESS_LOG_LIMIT:]
    progress.update(progress_updates)
    _persist_task_progress(task.parse_task_id, db=db, llm_progress=progress)


def _set_task_phase(
    task: ActualBidParseTask,
    db: Session,
    phase: ActualBidParseTaskPhase,
    *,
    message: str | None = None,
    **progress_updates,
) -> None:
    if message:
        _append_parse_log(task, db, message, phase=phase.value, **progress_updates)
        _persist_task_progress(task.parse_task_id, db=db, task_phase=phase)
    else:
        progress = _load_progress(task.parse_task_id, db)
        progress["phase"] = phase.value
        progress.update(progress_updates)
        _persist_task_progress(task.parse_task_id, db=db, task_phase=phase, llm_progress=progress, **progress_updates)


def _record_phase_timing(task: ActualBidParseTask, db: Session, phase_key: str, elapsed_ms: int) -> None:
    progress = _load_progress(task.parse_task_id, db)
    timings = dict(progress.get("phase_timings_ms") or {})
    timings[phase_key] = elapsed_ms
    progress["phase_timings_ms"] = timings
    _persist_task_progress(task.parse_task_id, db=db, llm_progress=progress)


@contextmanager
def _timed_step(
    task: ActualBidParseTask,
    db: Session,
    step: str,
    *,
    user_visible: bool = False,
    **start_context,
) -> Iterator[None]:
    """Log step start/end to backend logger; optionally mirror to task progress."""
    task_id = task.parse_task_id
    ctx = ", ".join(f"{key}={value}" for key, value in start_context.items()) if start_context else ""
    logger.info("actual_bid_parse task=%s [%s] START%s", task_id, step, f" ({ctx})" if ctx else "")
    if user_visible:
        _append_parse_log(task, db, f"[开始] {step}" + (f"（{ctx}）" if ctx else ""))
    started = time.perf_counter()
    try:
        yield
    except Exception:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            "actual_bid_parse task=%s [%s] FAILED elapsed_ms=%d",
            task_id,
            step,
            elapsed_ms,
        )
        if user_visible:
            db.rollback()
            _append_parse_log(task, db, f"[失败] {step}（{elapsed_ms / 1000:.1f}s）", level="error")
        raise
    else:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "actual_bid_parse task=%s [%s] DONE elapsed_ms=%d",
            task_id,
            step,
            elapsed_ms,
        )
        if user_visible:
            _append_parse_log(task, db, f"[完成] {step}（{elapsed_ms / 1000:.1f}s）")


def _commit_parse_checkpoint(
    db: Session,
    *,
    task: ActualBidParseTask,
    entry: DownstreamTaskEntry,
    file_import: FileImport,
    document: Document | None = None,
) -> None:
    """Commit incremental progress so progress writes do not deadlock long transactions."""
    db.commit()
    db.refresh(task)
    db.refresh(entry)
    db.refresh(file_import)
    if document is not None:
        db.refresh(document)


def _resolve_docx_path(file_import: FileImport) -> Path:
    source = Path(Settings().storage_root) / file_import.storage_path
    if source.suffix.lower() == ".docm":
        return ensure_docx_for_parse(source)
    return source


def _get_or_create_parse_task(
    db: Session,
    *,
    entry: DownstreamTaskEntry,
    file_import: FileImport,
) -> ActualBidParseTask:
    payload = dict(entry.payload or {})
    parse_task_id = payload.get("parse_task_id")
    task: ActualBidParseTask | None = None
    if parse_task_id:
        try:
            task = db.get(ActualBidParseTask, uuid.UUID(str(parse_task_id)))
        except (TypeError, ValueError):
            task = None
    if task is None:
        task = ActualBidParseTask(
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            status=ActualBidParseTaskStatus.pending,
            parse_strategy=ActualBidParseStrategy.docx,
            trace_id=uuid.uuid4(),
            created_by=file_import.confirmed_by or file_import.created_by or "system",
        )
        db.add(task)
        db.flush()
        payload["parse_task_id"] = str(task.parse_task_id)
        entry.payload = payload
    return task


def _clear_document_tree_for_reparse(
    db: Session,
    *,
    kb_id: uuid.UUID,
    document_id: uuid.UUID,
    import_id: uuid.UUID,
) -> int:
    """Remove dependent rows before rebuilding Document Tree on force reparse."""
    outline_ids = [
        row[0]
        for row in db.query(BidOutline.bid_outline_id)
        .filter(BidOutline.kb_id == kb_id, BidOutline.source_doc_id == document_id)
        .all()
    ]
    preserve_outline_nodes = False
    if outline_ids:
        preserve_outline_nodes = (
            db.query(BidOutline.bid_outline_id)
            .filter(
                BidOutline.bid_outline_id.in_(outline_ids),
                BidOutline.structure_locked_at.isnot(None),
            )
            .first()
            is not None
        )
    if outline_ids:
        outline_node_query = db.query(BidOutlineNode).filter(BidOutlineNode.bid_outline_id.in_(outline_ids))
        if preserve_outline_nodes:
            outline_node_query.update({BidOutlineNode.source_node_id: None}, synchronize_session=False)
        else:
            outline_node_query.delete(synchronize_session=False)

    db.query(CandidateKnowledge).filter(
        CandidateKnowledge.kb_id == kb_id,
        CandidateKnowledge.import_id == import_id,
        CandidateKnowledge.source_doc_id == document_id,
    ).delete(synchronize_session=False)
    db.query(DocumentMediaAsset).filter(DocumentMediaAsset.document_id == document_id).delete(
        synchronize_session=False
    )

    db.query(DocumentTreeNode).filter(DocumentTreeNode.document_id == document_id).update(
        {DocumentTreeNode.parent_id: None},
        synchronize_session=False,
    )
    deleted = db.query(DocumentTreeNode).filter(DocumentTreeNode.document_id == document_id).delete(
        synchronize_session=False
    )
    db.flush()
    return deleted


def _persist_document_media_assets(
    db: Session,
    *,
    file_import: FileImport,
    document: Document,
    docx_path: Path,
) -> dict[int, list[uuid.UUID]]:
    extracted = extract_docx_images(
        docx_path,
        storage_root=Path(Settings().storage_root),
        kb_id=file_import.kb_id,
        document_id=document.document_id,
    )
    if not extracted:
        return {}

    assets = [
        DocumentMediaAsset(
            asset_id=item.asset_id,
            kb_id=file_import.kb_id,
            document_id=document.document_id,
            storage_path=item.storage_path,
            mime_type=item.mime_type,
            source_block_index=item.source_block_index,
        )
        for item in extracted
    ]
    db.add_all(assets)
    db.flush()

    by_block_index: dict[int, list[uuid.UUID]] = {}
    for item in extracted:
        by_block_index.setdefault(item.source_block_index, []).append(item.asset_id)
    return by_block_index


def _persist_document_tree(
    db: Session,
    *,
    file_import: FileImport,
    task: ActualBidParseTask,
    walked_nodes,
    docx_path: Path,
) -> tuple[Document, dict[str, uuid.UUID]]:
    total_nodes = len(walked_nodes)
    logger.info(
        "actual_bid_parse task=%s persist_document_tree START total_nodes=%d import_id=%s",
        task.parse_task_id,
        total_nodes,
        file_import.import_id,
    )

    with _timed_step(task, db, "document_tree.prepare_record"):
        document = (
            db.query(Document)
            .filter(Document.kb_id == file_import.kb_id, Document.import_id == file_import.import_id)
            .order_by(Document.created_at.desc())
            .first()
        )
        if document is None:
            document = Document(
                kb_id=file_import.kb_id,
                import_id=file_import.import_id,
                source_type=DocumentSourceType.actual_bid,
                document_name=file_import.file_name,
                parse_status=DocumentParseStatus.pending,
                product_category_ids=file_import.product_category_ids or [],
                created_by=file_import.confirmed_by or file_import.created_by or "system",
            )
            db.add(document)
            db.flush()

        document.document_name = file_import.file_name
        document.parse_status = DocumentParseStatus.parsing
        document.product_category_ids = file_import.product_category_ids or []

    with _timed_step(task, db, "document_tree.delete_old_nodes", document_id=str(document.document_id)):
        deleted = _clear_document_tree_for_reparse(
            db,
            kb_id=file_import.kb_id,
            document_id=document.document_id,
            import_id=file_import.import_id,
        )
        logger.info(
            "actual_bid_parse task=%s document_tree.delete_old_nodes deleted=%d",
            task.parse_task_id,
            deleted,
        )

    with _timed_step(task, db, "document_tree.extract_docx_images"):
        image_asset_ids_by_block = _persist_document_media_assets(
            db,
            file_import=file_import,
            document=document,
            docx_path=docx_path,
        )

    _set_task_phase(
        task,
        db,
        ActualBidParseTaskPhase.document_parse,
        message=f"写入 Document Tree（共 {total_nodes} 节点）",
        total_nodes=total_nodes,
        processed_nodes=0,
    )

    node_id_by_temp_id: dict[str, uuid.UUID] = {}
    parent_temp_id_by_temp_id: dict[str, str | None] = {}
    db_nodes: list[DocumentTreeNode] = []
    logger.info(
        "actual_bid_parse task=%s document_tree.build_nodes START total_nodes=%d",
        task.parse_task_id,
        total_nodes,
    )
    build_started = time.perf_counter()
    for index, node in enumerate(walked_nodes):
        try:
            node_type = DocumentTreeNodeType(node.node_type)
        except ValueError:
            node_type = DocumentTreeNodeType.other
        safe_text = sanitize_pg_text(node.text)
        title = safe_text[:512] if node_type == DocumentTreeNodeType.heading and safe_text else None
        content_ref = node.temp_id
        if node_type == DocumentTreeNodeType.image and node.source_block_index is not None:
            matched_assets = image_asset_ids_by_block.get(node.source_block_index) or []
            if matched_assets:
                content_ref = str(matched_assets.pop(0))
        node_id = uuid.uuid4()
        node_id_by_temp_id[node.temp_id] = node_id
        parent_temp_id_by_temp_id[node.temp_id] = node.parent_temp_id
        db_nodes.append(
            DocumentTreeNode(
                node_id=node_id,
                kb_id=file_import.kb_id,
                document_id=document.document_id,
                parent_id=None,
                node_type=node_type,
                title=title,
                level=node.level if node.level > 0 else None,
                sort_order=max(int(node.sort_order), 0),
                content_ref=content_ref,
                content_preview=safe_text[:4000] if safe_text else None,
                chapter_taxonomy_id=None,
                product_category_ids=[],
                is_outline_node=bool(node.is_outline_node),
                candidate_template_chapter_id=None,
                candidate_pattern_id=None,
                needs_manual_review=bool(node.needs_manual_review),
                tree_version=document.tree_version,
            )
        )
        if (index + 1) % _PERSIST_PROGRESS_INTERVAL == 0:
            logger.info(
                "actual_bid_parse task=%s document_tree.build_nodes progress=%d/%d",
                task.parse_task_id,
                index + 1,
                total_nodes,
            )
            _append_parse_log(
                task,
                db,
                f"构建节点对象 {index + 1}/{total_nodes}",
                processed_nodes=index + 1,
                total_nodes=total_nodes,
            )

    build_elapsed_ms = int((time.perf_counter() - build_started) * 1000)
    logger.info(
        "actual_bid_parse task=%s document_tree.build_nodes DONE count=%d elapsed_ms=%d",
        task.parse_task_id,
        len(db_nodes),
        build_elapsed_ms,
    )

    with _timed_step(task, db, "document_tree.db_add_all", node_count=len(db_nodes)):
        db.add_all(db_nodes)
        db.flush()

    with _timed_step(task, db, "document_tree.link_parents", node_count=len(db_nodes)):
        linked = 0
        for temp_id, parent_temp_id in parent_temp_id_by_temp_id.items():
            parent_id = node_id_by_temp_id.get(parent_temp_id) if parent_temp_id else None
            if parent_id is None:
                continue
            db.query(DocumentTreeNode).filter(
                DocumentTreeNode.node_id == node_id_by_temp_id[temp_id]
            ).update({"parent_id": parent_id}, synchronize_session=False)
            linked += 1
        db.flush()
        logger.info(
            "actual_bid_parse task=%s document_tree.link_parents linked=%d",
            task.parse_task_id,
            linked,
        )

    _append_parse_log(
        task,
        db,
        f"Document Tree 写入完成（{total_nodes} 节点）",
        processed_nodes=total_nodes,
        total_nodes=total_nodes,
    )
    logger.info(
        "actual_bid_parse task=%s persist_document_tree DONE document_id=%s",
        task.parse_task_id,
        document.document_id,
    )

    task.document_id = document.document_id
    return document, node_id_by_temp_id


def _persist_parse_suggestion(
    db: Session,
    *,
    task: ActualBidParseTask,
    document: Document,
    walked,
    toc_result,
    generated_candidate_count: int,
    outline_quality: dict | None = None,
    filter_decisions: list | None = None,
) -> None:
    suggestion = (
        db.query(DocumentParseSuggestion)
        .filter(DocumentParseSuggestion.parse_task_id == task.parse_task_id)
        .one_or_none()
    )
    if suggestion is None:
        suggestion = DocumentParseSuggestion(
            kb_id=task.kb_id,
            parse_task_id=task.parse_task_id,
            document_id=document.document_id,
        )
        db.add(suggestion)
    suggestion.document_id = document.document_id
    hierarchy_inference = None
    infer_result = getattr(walked, "infer_result", None)
    if infer_result is not None:
        hierarchy_inference = {
            "heading_count": len(infer_result.headings),
            "patterns_used": infer_result.patterns_used,
            "used_flat_fallback": infer_result.used_flat_fallback,
            "medium_confidence_count": infer_result.medium_confidence_count,
        }
    suggestion.payload = {
        "outline_extract_strategy": toc_result.strategy.value,
        "walk_result": {
            "node_count": len(walked.nodes),
            "used_flat_fallback": walked.used_flat_fallback,
            "needs_manual_review": walked.needs_manual_review,
        },
        "hierarchy_inference": hierarchy_inference,
        "chunk_classification": {
            "mode": "skipped",
            "suggestion_source": "rule",
            "reason": "P1 runner uses rule-only fallback metadata",
        },
        "candidate_count": generated_candidate_count,
    }
    if outline_quality is not None:
        suggestion.payload["outline_quality"] = outline_quality
        suggestion.payload["filtered_total"] = outline_quality.get("filter_stats", {}).get("excluded", 0)
    if filter_decisions is not None:
        suggestion.payload["filter_decisions_sample"] = sample_excluded_decisions(filter_decisions)


def enqueue_actual_bid_parse(
    db: Session,
    *,
    kb_id: uuid.UUID,
    import_id: uuid.UUID,
    operator_id: str,
    trace_id: uuid.UUID | None,
    force_reparse: bool = False,
) -> ActualBidParseTask:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise ActualBidParseServiceError("File import not found", code="NOT_FOUND", status_code=404)
    if record.status != FileImportStatus.confirmed or record.file_purpose != FilePurpose.actual_bid:
        raise ActualBidParseServiceError(
            "Import must be confirmed actual_bid",
            code="IMPORT_NOT_CONFIRMED",
            status_code=422,
        )

    running = (
        db.query(ActualBidParseTask)
        .filter(
            ActualBidParseTask.kb_id == kb_id,
            ActualBidParseTask.import_id == import_id,
            ActualBidParseTask.status.in_(
                [ActualBidParseTaskStatus.pending, ActualBidParseTaskStatus.running]
            ),
        )
        .first()
    )
    if running and not force_reparse:
        raise ActualBidParseServiceError(
            "Parse task is already in progress",
            code="PARSE_IN_PROGRESS",
            status_code=409,
        )

    task = ActualBidParseTask(
        kb_id=kb_id,
        import_id=import_id,
        status=ActualBidParseTaskStatus.pending,
        parse_strategy=ActualBidParseStrategy.docx,
        trace_id=trace_id or uuid.uuid4(),
        created_by=operator_id,
    )
    db.add(task)
    db.flush()

    pending_entry = (
        db.query(DownstreamTaskEntry)
        .filter(
            DownstreamTaskEntry.kb_id == kb_id,
            DownstreamTaskEntry.import_id == import_id,
            DownstreamTaskEntry.task_type == DownstreamTaskType.document_parse,
            DownstreamTaskEntry.status == DownstreamTaskStatus.pending,
        )
        .order_by(DownstreamTaskEntry.created_at.asc())
        .first()
    )
    if pending_entry is None:
        pending_entry = DownstreamTaskEntry(
            kb_id=kb_id,
            import_id=import_id,
            task_type=DownstreamTaskType.document_parse,
            status=DownstreamTaskStatus.pending,
            payload={},
        )
        db.add(pending_entry)
        db.flush()
    payload = dict(pending_entry.payload or {})
    payload["parse_task_id"] = str(task.parse_task_id)
    payload["enqueued_by"] = operator_id
    payload["force_reparse"] = bool(force_reparse)
    pending_entry.payload = payload

    db.commit()
    db.refresh(task)
    return task


def _run_entry(db: Session, entry: DownstreamTaskEntry) -> None:
    logger.info(
        "actual_bid_parse _run_entry START entry_id=%s import_id=%s task_type=%s",
        entry.entry_id,
        entry.import_id,
        entry.task_type,
    )
    file_import = db.get(FileImport, entry.import_id)
    if file_import is None:
        logger.error("actual_bid_parse _run_entry file_import missing import_id=%s", entry.import_id)
        entry.status = DownstreamTaskStatus.failed
        db.commit()
        return

    task = _get_or_create_parse_task(db, entry=entry, file_import=file_import)
    force_reparse = bool((entry.payload or {}).get("force_reparse"))
    logger.info(
        "actual_bid_parse task=%s _run_entry parse_task ready force_reparse=%s file=%s",
        task.parse_task_id,
        force_reparse,
        file_import.file_name,
    )
    task.status = ActualBidParseTaskStatus.running
    task.parse_strategy = ActualBidParseStrategy.docx
    task.started_at = _now()
    task.finished_at = None
    task.error_message = None
    task.task_phase = ActualBidParseTaskPhase.document_parse

    try:
        if file_import.file_type != FileType.docx:
            raise ValueError("Only docx is supported in P1")

        source_path = Path(Settings().storage_root) / file_import.storage_path
        if source_path.suffix.lower() == ".docm":
            _append_parse_log(task, db, f"检测到 docm，开始转换为 docx（{source_path.name}）")
        docx_path = _resolve_docx_path(file_import)
        if not docx_path.exists():
            raise FileNotFoundError(f"File not found: {docx_path}")
        if docx_path != source_path:
            _append_parse_log(
                task,
                db,
                f"docm 转换完成，使用 {docx_path.name}（{docx_path.stat().st_size / (1024 * 1024):.1f} MB）",
            )

        file_size_bytes = docx_path.stat().st_size
        initial_progress = _init_progress(file_size_bytes=file_size_bytes)
        _persist_task_progress(
            task.parse_task_id,
            db=db,
            status=ActualBidParseTaskStatus.running,
            task_phase=ActualBidParseTaskPhase.document_parse,
            message=f"开始解析 {file_import.file_name}（{file_size_bytes / (1024 * 1024):.1f} MB）",
            llm_progress=initial_progress,
        )
        db.commit()
        db.refresh(task)
        db.refresh(entry)
        db.refresh(file_import)

        # Phase 1: walk_document -> persist document + tree nodes
        def _on_walk_progress(block_count: int) -> None:
            if block_count % (_WALK_PROGRESS_INTERVAL * 5) == 0:
                logger.info(
                    "actual_bid_parse task=%s walk_document progress blocks=%d",
                    task.parse_task_id,
                    block_count,
                )
            _append_parse_log(
                task,
                db,
                f"遍历文档块 {block_count}",
                processed_nodes=block_count,
            )

        walk_started = time.perf_counter()
        with _timed_step(
            task,
            db,
            "walk_document",
            user_visible=True,
            path=str(docx_path),
            file_size_mb=f"{file_size_bytes / (1024 * 1024):.1f}",
        ):
            walked = walk_document(
                docx_path,
                on_block_progress=_on_walk_progress,
                block_progress_interval=_WALK_PROGRESS_INTERVAL,
            )
        walk_elapsed_ms = int((time.perf_counter() - walk_started) * 1000)
        _record_phase_timing(task, db, "document_walk", walk_elapsed_ms)
        node_count = len(walked.nodes)
        _append_parse_log(
            task,
            db,
            (
                f"文档遍历完成：{node_count} 节点，"
                f"flat_fallback={walked.used_flat_fallback}，"
                f"needs_manual_review={walked.needs_manual_review}"
            ),
            total_nodes=node_count,
        )
        logger.info(
            "actual_bid_parse task=%s walk_document result nodes=%d flat_fallback=%s needs_review=%s",
            task.parse_task_id,
            node_count,
            walked.used_flat_fallback,
            walked.needs_manual_review,
        )
        if node_count > _MAX_WALK_NODES:
            raise ValueError(
                f"文档节点数异常（{node_count} > {_MAX_WALK_NODES}），"
                "可能未正确解析 docm/docx，请检查文件格式或联系管理员"
            )

        persist_started = time.perf_counter()
        with _timed_step(
            task,
            db,
            "persist_document_tree",
            user_visible=True,
            node_count=len(walked.nodes),
        ):
            document, source_node_by_temp_id = _persist_document_tree(
                db,
                file_import=file_import,
                task=task,
                walked_nodes=walked.nodes,
                docx_path=docx_path,
            )
        persist_elapsed_ms = int((time.perf_counter() - persist_started) * 1000)
        _record_phase_timing(task, db, "persist_tree", persist_elapsed_ms)
        _commit_parse_checkpoint(db, task=task, entry=entry, file_import=file_import, document=document)

        # Phase 2: extract_toc_entries -> persist bid outline
        _set_task_phase(
            task,
            db,
            ActualBidParseTaskPhase.bid_outline_extract,
            message="提取目录结构",
        )
        with _timed_step(task, db, "extract_toc_entries", user_visible=True, path=str(docx_path)):
            raw_toc = extract_toc_entries(docx_path, infer_snapshot=walked)
            filter_result = filter_outline_entries(
                raw_toc.entries,
                blocks=walked.collected.blocks if walked.collected else [],
                strategy=raw_toc.strategy,
            )
            outline_quality = summarize_outline_quality(
                filter_result.kept,
                strategy=raw_toc.strategy,
                filter_stats=filter_result.stats,
                raw_count=len(raw_toc.entries),
                embedded_regions=(
                    walked.infer_result.embedded_regions if walked.infer_result else None
                ),
                embedded_heading_count=(
                    walked.infer_result.embedded_heading_count if walked.infer_result else 0
                ),
            )
            toc_result = TocExtractResult(entries=filter_result.kept, strategy=raw_toc.strategy)
            filter_decisions = filter_result.decisions
        logger.info(
            "actual_bid_parse task=%s extract_toc_entries result entries=%d raw=%d excluded=%d strategy=%s",
            task.parse_task_id,
            len(toc_result.entries),
            len(raw_toc.entries),
            filter_result.stats.excluded,
            toc_result.strategy.value,
        )
        db.commit()
        db.refresh(task)

        existing_outline = (
            db.query(BidOutline)
            .filter(BidOutline.kb_id == file_import.kb_id, BidOutline.source_doc_id == document.document_id)
            .order_by(BidOutline.created_at.desc())
            .first()
        )
        if force_reparse and existing_outline is not None and existing_outline.structure_locked_at:
            with _timed_step(
                task,
                db,
                "bid_outline.generate_structure_diff",
                user_visible=True,
                bid_outline_id=str(existing_outline.bid_outline_id),
            ):
                bid_outline_diff_service.generate_structure_diff(
                    db,
                    kb_id=file_import.kb_id,
                    bid_outline_id=existing_outline.bid_outline_id,
                    parse_task_id=task.parse_task_id,
                    document_id=document.document_id,
                    toc_entries=toc_result.entries,
                    source_node_by_temp_id=source_node_by_temp_id,
                )
            task.bid_outline_id = existing_outline.bid_outline_id
        else:
            with _timed_step(
                task,
                db,
                "bid_outline.persist_outline",
                user_visible=True,
                toc_entries=len(toc_result.entries),
            ):
                outline_result = bid_outline_extract_service.persist_outline(
                    db,
                    kb_id=file_import.kb_id,
                    import_id=file_import.import_id,
                    document_id=document.document_id,
                    outline_name=document.document_name,
                    toc_entries=toc_result.entries,
                    source_node_by_temp_id=source_node_by_temp_id,
                    created_by=file_import.confirmed_by or file_import.created_by or "system",
                    extract_strategy=toc_result.strategy.value,
                    product_category_ids=file_import.product_category_ids or [],
                    project_name=document.bid_project_name,
                    customer_name=document.bid_customer_name,
                )
            task.bid_outline_id = outline_result.bid_outline.bid_outline_id
            logger.info(
                "actual_bid_parse task=%s bid_outline.persist_outline bid_outline_id=%s",
                task.parse_task_id,
                task.bid_outline_id,
            )

        _commit_parse_checkpoint(db, task=task, entry=entry, file_import=file_import, document=document)
        _append_parse_log(
            task,
            db,
            f"目录抽取完成：{len(toc_result.entries)} 条目，策略 {toc_result.strategy.value}",
        )

        # Phase 3: candidate_generate_service.generate
        _set_task_phase(
            task,
            db,
            ActualBidParseTaskPhase.candidate_generate,
            message="生成候选知识",
        )
        with _timed_step(task, db, "candidate_generate", user_visible=True, document_id=str(document.document_id)):
            created_candidates = candidate_generate_service.generate_for_document(
                db,
                kb_id=file_import.kb_id,
                import_id=file_import.import_id,
                document_id=document.document_id,
                parse_task_id=task.parse_task_id,
            )
        _append_parse_log(
            task,
            db,
            f"候选知识生成完成：{len(created_candidates)} 条",
            candidate_count=len(created_candidates),
        )
        logger.info(
            "actual_bid_parse task=%s candidate_generate count=%d",
            task.parse_task_id,
            len(created_candidates),
        )

        with _timed_step(task, db, "finalize.parse_suggestion"):
            document.parse_status = DocumentParseStatus.ready
            _persist_parse_suggestion(
                db,
                task=task,
                document=document,
                walked=walked,
                toc_result=toc_result,
                generated_candidate_count=len(created_candidates),
                outline_quality=outline_quality,
                filter_decisions=filter_decisions,
            )

        task.status = ActualBidParseTaskStatus.ready
        task.task_phase = ActualBidParseTaskPhase.full_pipeline
        task.finished_at = _now()
        total_elapsed_ms = _elapsed_ms(task.started_at, task.finished_at)
        _append_parse_log(
            task,
            db,
            f"解析流水线完成，总耗时 {total_elapsed_ms / 1000:.1f}s",
            phase=ActualBidParseTaskPhase.full_pipeline.value,
        )
        logger.info(
            "actual_bid_parse task=%s pipeline DONE total_elapsed_ms=%d document_id=%s bid_outline_id=%s",
            task.parse_task_id,
            total_elapsed_ms,
            task.document_id,
            task.bid_outline_id,
        )

        with _timed_step(task, db, "finalize.commit_downstream"):
            downstream_entries = (
                db.query(DownstreamTaskEntry)
                .filter(
                    DownstreamTaskEntry.kb_id == file_import.kb_id,
                    DownstreamTaskEntry.import_id == file_import.import_id,
                    DownstreamTaskEntry.task_type.in_(
                        [
                            DownstreamTaskType.document_parse,
                            DownstreamTaskType.bid_outline_extract,
                            DownstreamTaskType.candidate_knowledge_generate,
                        ]
                    ),
                )
                .all()
            )
            task.downstream_entry_ids = [str(item.entry_id) for item in downstream_entries]
            for item in downstream_entries:
                item.status = DownstreamTaskStatus.completed
            task.llm_progress = _load_progress(task.parse_task_id, db)
            db.commit()
        logger.info("actual_bid_parse task=%s _run_entry SUCCESS", task.parse_task_id)
    except Exception as exc:
        task_id = task.parse_task_id
        entry_id = entry.entry_id
        logger.exception("actual_bid_parse task=%s failed", task_id)
        db.rollback()
        task = db.get(ActualBidParseTask, task_id)
        entry = db.get(DownstreamTaskEntry, entry_id)
        if task is not None:
            task.status = ActualBidParseTaskStatus.failed
            task.error_message = str(exc)
            task.finished_at = _now()
            progress = _load_progress(task.parse_task_id, db)
            logs = list(progress.get("logs") or [])
            logs.append(
                {
                    "ts": _now().isoformat(),
                    "level": "error",
                    "message": f"解析失败: {exc}",
                }
            )
            progress["logs"] = logs[-_PROGRESS_LOG_LIMIT:]
            task.llm_progress = progress
        if entry is not None:
            entry.status = DownstreamTaskStatus.failed
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.warning(
                "actual_bid_parse task=%s could not persist failure state in main session",
                task_id,
            )
            _persist_task_progress(
                task_id,
                status=ActualBidParseTaskStatus.failed,
                message=f"解析失败: {exc}",
                level="error",
            )


def run_actual_bid_parse_once(db: Session) -> bool:
    entry = (
        db.query(DownstreamTaskEntry)
        .filter(
            DownstreamTaskEntry.task_type == DownstreamTaskType.document_parse,
            DownstreamTaskEntry.status == DownstreamTaskStatus.pending,
        )
        .order_by(DownstreamTaskEntry.created_at.asc())
        .first()
    )
    if entry is None:
        logger.debug("actual_bid_parse runner no pending document_parse entry")
        return False

    logger.info(
        "actual_bid_parse runner claiming entry_id=%s import_id=%s",
        entry.entry_id,
        entry.import_id,
    )
    entry.status = DownstreamTaskStatus.claimed
    entry.claimed_by = "actual_bid_parse_runner"
    entry.claimed_at = _now()
    db.flush()
    _run_entry(db, entry)
    return True


def run_actual_bid_parse_pending(db: Session) -> None:
    processed = 0
    while run_actual_bid_parse_once(db):
        processed += 1
    if processed:
        logger.info("actual_bid_parse runner processed %d entries", processed)


def run_actual_bid_parse_in_new_session() -> None:
    logger.info("actual_bid_parse background runner START")
    try:
        db = SessionLocal()
    except Exception:
        logger.exception("actual_bid_parse runner could not open DB session")
        return
    try:
        run_actual_bid_parse_pending(db)
    except Exception:
        logger.exception("actual_bid_parse runner failed")
        db.rollback()
    finally:
        db.close()
        logger.info("actual_bid_parse background runner END")
