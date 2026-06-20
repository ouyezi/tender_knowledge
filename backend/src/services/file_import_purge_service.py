from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.config import Settings
from src.models.document import Document
from src.models.document_media_asset import DocumentMediaAsset
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.document_tree_node import DocumentTreeNode
from src.models.downstream_task_entry import DownstreamTaskEntry
from src.models.file_import import FileImport, FileImportStatus
from src.models.file_purpose_suggestion import FilePurposeSuggestion
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.models.import_task import ImportTask


class FileImportPurgeServiceError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        details: dict | None = None,
    ):
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


@dataclass
class PurgeSummary:
    import_id: str
    file_name: str
    status: str = "deleted"
    deleted_counts: dict[str, int] = field(default_factory=dict)
    deprecated_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class PurgeImpactReport:
    import_id: str
    file_name: str
    has_published_assets: bool
    published_counts: dict[str, int]
    published_total: int
    intermediate_counts: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "import_id": self.import_id,
            "file_name": self.file_name,
            "has_published_assets": self.has_published_assets,
            "published_counts": self.published_counts,
            "published_total": self.published_total,
            "intermediate_counts": self.intermediate_counts,
        }


def _inc(counts: dict[str, int], key: str, n: int) -> None:
    if n > 0:
        counts[key] = counts.get(key, 0) + n


def _delete_storage_dir(kb_id: UUID, import_id: UUID) -> bool:
    path = Path(Settings().storage_root) / str(kb_id) / str(import_id)
    if not path.exists():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True


def check_purge_impact(db: Session, *, kb_id: UUID, import_id: UUID) -> PurgeImpactReport:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise FileImportPurgeServiceError("File import not found", code="NOT_FOUND", status_code=404)
    doc_count = db.query(Document).filter(Document.import_id == import_id).count()
    task_count = db.query(ImportTask).filter(ImportTask.import_id == import_id).count()
    return PurgeImpactReport(
        import_id=str(import_id),
        file_name=record.file_name,
        has_published_assets=False,
        published_counts={},
        published_total=0,
        intermediate_counts={"documents": doc_count, "import_tasks": task_count},
    )


def purge_file_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    operator_id: str,
    trace_id: UUID | None,
    deprecate_published: bool = False,
) -> PurgeSummary:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise FileImportPurgeServiceError("File import not found", code="NOT_FOUND", status_code=404)
    if record.status == FileImportStatus.deleted:
        return PurgeSummary(import_id=str(import_id), file_name=record.file_name)

    counts: dict[str, int] = {}
    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.delete,
            payload_summary={
                "file_name": record.file_name,
                "deprecate_published": deprecate_published,
            },
        )
    )

    document_ids = [
        row.document_id for row in db.query(Document).filter(Document.import_id == import_id).all()
    ]
    if document_ids:
        _inc(
            counts,
            "document_tree_nodes",
            db.query(DocumentTreeNode)
            .filter(DocumentTreeNode.document_id.in_(document_ids))
            .delete(synchronize_session=False),
        )
        _inc(
            counts,
            "document_media_assets",
            db.query(DocumentMediaAsset)
            .filter(DocumentMediaAsset.document_id.in_(document_ids))
            .delete(synchronize_session=False),
        )
        _inc(
            counts,
            "document_parse_suggestions",
            db.query(DocumentParseSuggestion)
            .filter(DocumentParseSuggestion.document_id.in_(document_ids))
            .delete(synchronize_session=False),
        )
        _inc(
            counts,
            "documents",
            db.query(Document).filter(Document.document_id.in_(document_ids)).delete(
                synchronize_session=False
            ),
        )

    _inc(
        counts,
        "downstream_task_entries",
        db.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.import_id == import_id)
        .delete(synchronize_session=False),
    )
    _inc(
        counts,
        "import_tasks",
        db.query(ImportTask)
        .filter(ImportTask.import_id == import_id)
        .delete(synchronize_session=False),
    )
    _inc(
        counts,
        "file_purpose_suggestions",
        db.query(FilePurposeSuggestion)
        .filter(FilePurposeSuggestion.import_id == import_id)
        .delete(synchronize_session=False),
    )

    if _delete_storage_dir(kb_id, import_id):
        _inc(counts, "storage_dirs", 1)

    record.status = FileImportStatus.deleted
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    _inc(counts, "file_imports", 1)
    db.flush()

    return PurgeSummary(
        import_id=str(import_id),
        file_name=record.file_name,
        deleted_counts=counts,
        deprecated_counts={},
    )


def purge_all_file_imports(
    db: Session,
    *,
    kb_id: UUID,
    operator_id: str,
    trace_id: UUID | None,
) -> list[PurgeSummary]:
    rows = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.status != FileImportStatus.deleted)
        .order_by(FileImport.created_at.desc())
        .all()
    )
    summaries = [
        purge_file_import(
            db,
            kb_id=kb_id,
            import_id=row.import_id,
            operator_id=operator_id,
            trace_id=trace_id,
        )
        for row in rows
    ]
    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid4(),
            kb_id=kb_id,
            import_id=None,
            operator_id=operator_id,
            action=ImportAuditAction.purge_all,
            payload_summary={
                "purged_count": len(summaries),
                "import_ids": [item.import_id for item in summaries],
            },
        )
    )
    db.flush()
    return summaries
