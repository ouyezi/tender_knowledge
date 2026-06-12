from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

from sqlalchemy.orm import Session

from src.config import Settings
from src.db.session import SessionLocal
from src.models.actual_bid_parse_task import (
    ActualBidParseStrategy,
    ActualBidParseTask,
    ActualBidParseTaskStatus,
)
from src.models.bid_outline import BidOutline
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services import bid_outline_diff_service, bid_outline_extract_service, candidate_generate_service
from src.services.docx_document_walker import walk_document
from src.services.docx_toc_extractor import extract_toc_entries


class ActualBidParseServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_docx_path(file_import: FileImport) -> Path:
    return Path(Settings().storage_root) / file_import.storage_path


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


def _persist_document_tree(
    db: Session,
    *,
    file_import: FileImport,
    task: ActualBidParseTask,
    walked_nodes,
) -> tuple[Document, dict[str, uuid.UUID]]:
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
    db.query(DocumentTreeNode).filter(DocumentTreeNode.document_id == document.document_id).delete(
        synchronize_session=False
    )
    db.flush()

    node_id_by_temp_id: dict[str, uuid.UUID] = {}
    parent_temp_id_by_temp_id: dict[str, str | None] = {}
    for node in walked_nodes:
        try:
            node_type = DocumentTreeNodeType(node.node_type)
        except ValueError:
            node_type = DocumentTreeNodeType.other
        title = node.text[:512] if node_type == DocumentTreeNodeType.heading else None
        db_node = DocumentTreeNode(
            kb_id=file_import.kb_id,
            document_id=document.document_id,
            parent_id=None,
            node_type=node_type,
            title=title,
            level=node.level if node.level > 0 else None,
            sort_order=max(int(node.sort_order), 0),
            content_ref=node.temp_id,
            content_preview=node.text[:4000] if node.text else None,
            chapter_taxonomy_id=None,
            product_category_ids=[],
            is_outline_node=bool(node.is_outline_node),
            candidate_template_chapter_id=None,
            candidate_pattern_id=None,
            needs_manual_review=bool(node.needs_manual_review),
            tree_version=document.tree_version,
        )
        db.add(db_node)
        db.flush()
        node_id_by_temp_id[node.temp_id] = db_node.node_id
        parent_temp_id_by_temp_id[node.temp_id] = node.parent_temp_id

    for temp_id, parent_temp_id in parent_temp_id_by_temp_id.items():
        parent_id = node_id_by_temp_id.get(parent_temp_id) if parent_temp_id else None
        if parent_id is None:
            continue
        db.query(DocumentTreeNode).filter(DocumentTreeNode.node_id == node_id_by_temp_id[temp_id]).update(
            {"parent_id": parent_id},
            synchronize_session=False,
        )
    db.flush()

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
    suggestion.payload = {
        "outline_extract_strategy": toc_result.strategy.value,
        "walk_result": {
            "node_count": len(walked.nodes),
            "used_flat_fallback": walked.used_flat_fallback,
            "needs_manual_review": walked.needs_manual_review,
        },
        "chunk_classification": {
            "mode": "skipped",
            "suggestion_source": "rule",
            "reason": "P1 runner uses rule-only fallback metadata",
        },
        "candidate_count": generated_candidate_count,
    }


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
    file_import = db.get(FileImport, entry.import_id)
    if file_import is None:
        entry.status = DownstreamTaskStatus.failed
        db.commit()
        return

    task = _get_or_create_parse_task(db, entry=entry, file_import=file_import)
    force_reparse = bool((entry.payload or {}).get("force_reparse"))
    task.status = ActualBidParseTaskStatus.running
    task.parse_strategy = ActualBidParseStrategy.docx
    task.started_at = _now()
    task.finished_at = None
    task.error_message = None
    db.flush()

    try:
        if file_import.file_type != FileType.docx:
            raise ValueError("Only docx is supported in P1")

        docx_path = _resolve_docx_path(file_import)
        if not docx_path.exists():
            raise FileNotFoundError(f"File not found: {docx_path}")

        # 1) walk_document -> persist document + tree nodes
        walked = walk_document(docx_path)
        document, source_node_by_temp_id = _persist_document_tree(
            db,
            file_import=file_import,
            task=task,
            walked_nodes=walked.nodes,
        )

        # 2) extract_toc_entries -> persist bid outline
        toc_result = extract_toc_entries(docx_path)
        existing_outline = (
            db.query(BidOutline)
            .filter(BidOutline.kb_id == file_import.kb_id, BidOutline.source_doc_id == document.document_id)
            .order_by(BidOutline.created_at.desc())
            .first()
        )
        if force_reparse and existing_outline is not None and existing_outline.structure_locked_at:
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

        # 3) optional chunk classification -> currently skipped with rule-only suggestion payload
        # 4) candidate_generate_service.generate
        created_candidates = candidate_generate_service.generate_for_document(
            db,
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            document_id=document.document_id,
            parse_task_id=task.parse_task_id,
        )

        document.parse_status = DocumentParseStatus.ready
        _persist_parse_suggestion(
            db,
            task=task,
            document=document,
            walked=walked,
            toc_result=toc_result,
            generated_candidate_count=len(created_candidates),
        )

        # 5) actual_bid_parse_task.status = ready
        task.status = ActualBidParseTaskStatus.ready
        task.finished_at = _now()

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
        db.commit()
    except Exception as exc:
        task.status = ActualBidParseTaskStatus.failed
        task.error_message = str(exc)
        task.finished_at = _now()
        entry.status = DownstreamTaskStatus.failed
        db.commit()


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
        return False

    entry.status = DownstreamTaskStatus.claimed
    entry.claimed_by = "actual_bid_parse_runner"
    entry.claimed_at = _now()
    db.flush()
    _run_entry(db, entry)
    return True


def run_actual_bid_parse_pending(db: Session) -> None:
    while run_actual_bid_parse_once(db):
        pass


def run_actual_bid_parse_in_new_session() -> None:
    try:
        db = SessionLocal()
    except Exception:
        return
    try:
        run_actual_bid_parse_pending(db)
    except Exception:
        db.rollback()
    finally:
        db.close()
