from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.config import Settings
from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.chunk_asset import ChunkAsset
from src.models.chunk_embedding import ChunkEmbedding
from src.models.document import Document
from src.models.document_media_asset import DocumentMediaAsset
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.document_tree_node import DocumentTreeNode
from src.models.downstream_task_entry import DownstreamTaskEntry
from src.models.file_import import FileImport
from src.models.file_purpose_suggestion import FilePurposeSuggestion
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.models.import_task import ImportTask
from src.models.knowledge_chunk import KnowledgeChunk


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
    has_published_assets: bool = False
    published_counts: dict[str, int] = field(default_factory=dict)
    published_total: int = 0
    intermediate_counts: dict[str, int] = field(default_factory=dict)

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


def _delete_doc_chunk_workspace(kb_id: UUID, import_id: UUID) -> bool:
    path = Path(Settings().storage_root) / "doc_chunk_workspaces" / str(kb_id) / str(import_id)
    if not path.exists():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True


def _delete_document_storage(document_ids: list[UUID]) -> int:
    storage_root = Path(Settings().storage_root)
    removed = 0
    for doc_id in document_ids:
        path = storage_root / "documents" / str(doc_id)
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


def _collect_import_ids(db: Session, *, kb_id: UUID, import_id: UUID) -> list[UUID]:
    child_ids = [
        row.import_id
        for row in db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.parent_import_id == import_id)
        .all()
    ]
    ordered: list[UUID] = []
    for child_id in child_ids:
        ordered.extend(_collect_import_ids(db, kb_id=kb_id, import_id=child_id))
    ordered.append(import_id)
    return ordered


def _embedding_count_for_documents(db: Session, document_ids: list[UUID]) -> int:
    if not document_ids:
        return 0
    chunk_ids = [
        row.id for row in db.query(KnowledgeChunk.id).filter(KnowledgeChunk.doc_id.in_(document_ids)).all()
    ]
    asset_ids = [
        row.id for row in db.query(ChunkAsset.id).filter(ChunkAsset.doc_id.in_(document_ids)).all()
    ]
    filters = []
    if chunk_ids:
        filters.append(
            and_(ChunkEmbedding.object_type == "chunk", ChunkEmbedding.object_id.in_(chunk_ids))
        )
    if asset_ids:
        filters.append(
            and_(ChunkEmbedding.object_type == "asset", ChunkEmbedding.object_id.in_(asset_ids))
        )
    if not filters:
        return 0
    return db.query(ChunkEmbedding).filter(or_(*filters)).count()


def _purge_documents_for_import(
    db: Session, *, document_ids: list[UUID], counts: dict[str, int]
) -> None:
    if not document_ids:
        return

    chunk_ids = [
        row.id for row in db.query(KnowledgeChunk.id).filter(KnowledgeChunk.doc_id.in_(document_ids)).all()
    ]
    asset_ids = [
        row.id for row in db.query(ChunkAsset.id).filter(ChunkAsset.doc_id.in_(document_ids)).all()
    ]
    emb_filters = []
    if chunk_ids:
        emb_filters.append(
            and_(ChunkEmbedding.object_type == "chunk", ChunkEmbedding.object_id.in_(chunk_ids))
        )
    if asset_ids:
        emb_filters.append(
            and_(ChunkEmbedding.object_type == "asset", ChunkEmbedding.object_id.in_(asset_ids))
        )
    if emb_filters:
        _inc(
            counts,
            "chunk_embeddings",
            db.query(ChunkEmbedding).filter(or_(*emb_filters)).delete(synchronize_session=False),
        )

    _inc(
        counts,
        "chunk_assets",
        db.query(ChunkAsset)
        .filter(ChunkAsset.doc_id.in_(document_ids))
        .delete(synchronize_session=False),
    )
    _inc(
        counts,
        "knowledge_chunks",
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.doc_id.in_(document_ids))
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
        "documents",
        db.query(Document).filter(Document.document_id.in_(document_ids)).delete(
            synchronize_session=False
        ),
    )


def check_purge_impact(db: Session, *, kb_id: UUID, import_id: UUID) -> PurgeImpactReport:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise FileImportPurgeServiceError("File import not found", code="NOT_FOUND", status_code=404)

    import_ids = _collect_import_ids(db, kb_id=kb_id, import_id=import_id)
    document_ids = [
        row.document_id
        for row in db.query(Document).filter(Document.import_id.in_(import_ids)).all()
    ]
    chunk_count = (
        db.query(KnowledgeChunk).filter(KnowledgeChunk.doc_id.in_(document_ids)).count()
        if document_ids
        else 0
    )
    asset_count = (
        db.query(ChunkAsset).filter(ChunkAsset.doc_id.in_(document_ids)).count()
        if document_ids
        else 0
    )
    embedding_count = _embedding_count_for_documents(db, document_ids)
    doc_count = len(document_ids)
    task_count = db.query(ImportTask).filter(ImportTask.import_id.in_(import_ids)).count()
    parse_task_count = (
        db.query(ActualBidParseTask).filter(ActualBidParseTask.import_id.in_(import_ids)).count()
    )

    return PurgeImpactReport(
        import_id=str(import_id),
        file_name=record.file_name,
        has_published_assets=False,
        published_counts={},
        published_total=0,
        intermediate_counts={
            "documents": doc_count,
            "import_tasks": task_count,
            "knowledge_chunks": chunk_count,
            "chunk_assets": asset_count,
            "chunk_embeddings": embedding_count,
            "actual_bid_parse_tasks": parse_task_count,
        },
    )


def purge_file_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    operator_id: str,
    trace_id: UUID | None,
) -> PurgeSummary:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise FileImportPurgeServiceError("File import not found", code="NOT_FOUND", status_code=404)

    file_name = record.file_name
    import_ids = _collect_import_ids(db, kb_id=kb_id, import_id=import_id)
    counts: dict[str, int] = {}

    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.delete,
            payload_summary={"file_name": file_name},
        )
    )

    for iid in import_ids:
        document_ids = [
            row.document_id for row in db.query(Document).filter(Document.import_id == iid).all()
        ]
        _purge_documents_for_import(db, document_ids=document_ids, counts=counts)
        _inc(
            counts,
            "actual_bid_parse_tasks",
            db.query(ActualBidParseTask)
            .filter(ActualBidParseTask.import_id == iid)
            .delete(synchronize_session=False),
        )
        _inc(
            counts,
            "downstream_task_entries",
            db.query(DownstreamTaskEntry)
            .filter(DownstreamTaskEntry.import_id == iid)
            .delete(synchronize_session=False),
        )
        _inc(
            counts,
            "import_tasks",
            db.query(ImportTask)
            .filter(ImportTask.import_id == iid)
            .delete(synchronize_session=False),
        )
        _inc(
            counts,
            "file_purpose_suggestions",
            db.query(FilePurposeSuggestion)
            .filter(FilePurposeSuggestion.import_id == iid)
            .delete(synchronize_session=False),
        )
        if _delete_storage_dir(kb_id, iid):
            _inc(counts, "storage_dirs", 1)
        if _delete_doc_chunk_workspace(kb_id, iid):
            _inc(counts, "doc_chunk_workspaces", 1)
        _inc(counts, "document_storage_dirs", _delete_document_storage(document_ids))
        _inc(
            counts,
            "file_imports",
            db.query(FileImport)
            .filter(FileImport.kb_id == kb_id, FileImport.import_id == iid)
            .delete(synchronize_session=False),
        )

    db.flush()

    return PurgeSummary(
        import_id=str(import_id),
        file_name=file_name,
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
        .filter(FileImport.kb_id == kb_id)
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
