"""Unified doc_chunk parse runner for actual_bid and template_file."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.config import Settings
from src.db.session import SessionLocal
from src.models.actual_bid_parse_task import (
    ActualBidParseTask,
    ActualBidParseTaskPhase,
    ActualBidParseTaskStatus,
)
from src.models.document import Document
from src.models.document_tree_node import DocumentTreeNode
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.services.docm_converter import ensure_docx_for_parse
from src.services.doc_chunk.import_service import import_workspace_for_knowledge_entry
from src.services.doc_chunk.pipeline_runner import run_doc_chunk_pipeline
from src.services.doc_chunk.workspace_manager import (
    cleanup_workspace,
    ensure_workspace,
    workspace_path_for_task,
)

logger = logging.getLogger(__name__)


class DocumentParseServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_docx_path(file_import: FileImport) -> Path:
    storage_root = Path(Settings().storage_root)
    source_path = storage_root / file_import.storage_path
    return ensure_docx_for_parse(source_path)


def _clear_document_tree_for_reparse(
    db: Session, *, kb_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    db.query(DocumentTreeNode).filter(
        DocumentTreeNode.kb_id == kb_id,
        DocumentTreeNode.document_id == document_id,
    ).delete(synchronize_session=False)


def enqueue_document_parse(
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
        raise DocumentParseServiceError("File import not found", code="NOT_FOUND", status_code=404)
    if record.status != FileImportStatus.confirmed:
        raise DocumentParseServiceError(
            "Import must be confirmed", code="IMPORT_NOT_CONFIRMED", status_code=422
        )
    if record.file_purpose not in {FilePurpose.actual_bid, FilePurpose.template_file}:
        raise DocumentParseServiceError(
            "Unsupported file purpose", code="VALIDATION", status_code=422
        )

    active = (
        db.query(ActualBidParseTask)
        .filter(
            ActualBidParseTask.kb_id == kb_id,
            ActualBidParseTask.import_id == import_id,
            ActualBidParseTask.status.in_(
                [ActualBidParseTaskStatus.pending, ActualBidParseTaskStatus.running]
            ),
        )
        .all()
    )
    if active and not force_reparse:
        raise DocumentParseServiceError(
            "Parse task already running", code="PARSE_ALREADY_RUNNING", status_code=409
        )

    task = ActualBidParseTask(
        kb_id=kb_id,
        import_id=import_id,
        status=ActualBidParseTaskStatus.pending,
        created_by=operator_id,
    )
    db.add(task)
    db.flush()

    entry = DownstreamTaskEntry(
        kb_id=kb_id,
        import_id=import_id,
        task_type=DownstreamTaskType.document_parse,
        status=DownstreamTaskStatus.pending,
        payload={"parse_task_id": str(task.parse_task_id)},
    )
    db.add(entry)
    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid.uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.route,
            payload_summary={"parse_task_id": str(task.parse_task_id)},
        )
    )
    db.flush()
    return task


def _run_entry(db: Session, entry: DownstreamTaskEntry) -> None:
    file_import = db.get(FileImport, entry.import_id)
    if file_import is None:
        entry.status = DownstreamTaskStatus.failed
        return

    parse_task_id = uuid.UUID(entry.payload.get("parse_task_id", ""))
    task = db.get(ActualBidParseTask, parse_task_id)
    if task is None:
        entry.status = DownstreamTaskStatus.failed
        return

    task.status = ActualBidParseTaskStatus.running
    task.started_at = _now()
    task.task_phase = ActualBidParseTaskPhase.document_parse
    db.flush()

    workspace: Path | None = None
    try:
        if file_import.file_type != FileType.docx:
            raise ValueError("Only docx is supported")

        docx_path = _resolve_docx_path(file_import)
        if not docx_path.exists():
            raise FileNotFoundError(str(docx_path))

        storage_root = Path(Settings().storage_root)
        workspace = workspace_path_for_task(
            storage_root=storage_root,
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            parse_task_id=task.parse_task_id,
        )
        ensure_workspace(workspace, overwrite=True)

        existing_document = (
            db.query(Document)
            .filter(
                Document.kb_id == file_import.kb_id,
                Document.import_id == file_import.import_id,
            )
            .order_by(Document.created_at.desc())
            .first()
        )
        if existing_document is not None:
            _clear_document_tree_for_reparse(
                db,
                kb_id=file_import.kb_id,
                document_id=existing_document.document_id,
            )
            db.flush()

        run_doc_chunk_pipeline(docx_path, workspace)
        result = import_workspace_for_knowledge_entry(
            db,
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            workspace=workspace,
            file_import=file_import,
            document_id=existing_document.document_id if existing_document else None,
        )

        task.document_id = result.document_id
        task.status = ActualBidParseTaskStatus.completed
        task.finished_at = _now()
        task.task_phase = ActualBidParseTaskPhase.document_parse
        entry.status = DownstreamTaskStatus.completed
        file_import.status = FileImportStatus.completed
        db.commit()
    except Exception as exc:
        logger.exception("document_parse failed import_id=%s", file_import.import_id)
        task.status = ActualBidParseTaskStatus.failed
        task.error_message = str(exc)[:2000]
        task.finished_at = _now()
        entry.status = DownstreamTaskStatus.failed
        file_import.status = FileImportStatus.failed
        db.commit()
        raise
    finally:
        if workspace is not None:
            cleanup_workspace(workspace, on_success=True)


def run_document_parse_once(db: Session) -> bool:
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
    entry.claimed_by = "document_parse_runner"
    entry.claimed_at = _now()
    db.flush()
    _run_entry(db, entry)
    return True


def run_document_parse_pending(db: Session) -> None:
    while run_document_parse_once(db):
        pass


def run_document_parse_in_new_session() -> None:
    db = SessionLocal()
    try:
        run_document_parse_pending(db)
    except Exception:
        logger.exception("document_parse runner failed")
        db.rollback()
    finally:
        db.close()
