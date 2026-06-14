from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.config import Settings
from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.bid_outline_structure_diff import BidOutlineStructureDiff
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.candidate_knowledge_stub import CandidateKnowledgeStub
from src.models.classification_reference import ClassificationReference, ReferenceObjectType
from src.models.document import Document
from src.models.document_media_asset import DocumentMediaAsset
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.document_tree_node import DocumentTreeNode
from src.models.downstream_task_entry import DownstreamTaskEntry
from src.models.file_import import FileImport, FileImportStatus
from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus
from src.models.manual_asset import ManualAsset, ManualAssetStatus
from src.models.wiki import Wiki, WikiStatus
from src.models.file_purpose_suggestion import FilePurposeSuggestion
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.models.import_task import ImportTask
from src.models.template import Template
from src.models.template_audit_log import TemplateAuditLog
from src.models.template_library import TemplateLibrary
from src.models.template_chapter import TemplateChapter
from src.models.template_material import TemplateMaterial
from src.models.template_parse_suggestion import TemplateParseSuggestion
from src.models.template_parse_task import TemplateParseTask
from src.models.template_rule import TemplateRule
from src.models.template_structure_diff import TemplateStructureDiff
from src.models.template_variable import TemplateVariable
from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalObjectType
from src.services.retrieval.indexing.index_builder import IndexBuilder


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


def check_purge_impact(db: Session, *, kb_id: UUID, import_id: UUID) -> PurgeImpactReport:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise FileImportPurgeServiceError("File import not found", code="NOT_FOUND", status_code=404)
    if record.status == FileImportStatus.deleted:
        return PurgeImpactReport(
            import_id=str(import_id),
            file_name=record.file_name,
            has_published_assets=False,
            published_counts={},
            published_total=0,
            intermediate_counts={},
        )

    published_counts = {
        "ku": db.query(KnowledgeUnit)
        .filter(
            KnowledgeUnit.kb_id == kb_id,
            KnowledgeUnit.import_id == import_id,
            KnowledgeUnit.status == KnowledgeUnitStatus.published,
        )
        .count(),
        "wiki": db.query(Wiki)
        .filter(
            Wiki.kb_id == kb_id,
            Wiki.import_id == import_id,
            Wiki.status == WikiStatus.published,
        )
        .count(),
        "manual_asset": db.query(ManualAsset)
        .filter(
            ManualAsset.kb_id == kb_id,
            ManualAsset.import_id == import_id,
            ManualAsset.status == ManualAssetStatus.published,
        )
        .count(),
    }
    published_total = sum(published_counts.values())
    intermediate_counts = {
        "candidate_knowledges": db.query(CandidateKnowledge)
        .filter(CandidateKnowledge.import_id == import_id)
        .count(),
        "documents": db.query(Document).filter(Document.import_id == import_id).count(),
        "import_tasks": db.query(ImportTask).filter(ImportTask.import_id == import_id).count(),
    }
    return PurgeImpactReport(
        import_id=str(import_id),
        file_name=record.file_name,
        has_published_assets=published_total > 0,
        published_counts={k: v for k, v in published_counts.items() if v > 0},
        published_total=published_total,
        intermediate_counts={k: v for k, v in intermediate_counts.items() if v > 0},
    )


def _inc(counts: dict[str, int], key: str, n: int) -> None:
    counts[key] = counts.get(key, 0) + n


def _deprecate_published_assets(db: Session, *, kb_id: UUID, import_id: UUID) -> dict[str, int]:
    counts: dict[str, int] = {}
    now = datetime.now(timezone.utc)
    index_builder = IndexBuilder(db)

    kus = (
        db.query(KnowledgeUnit)
        .filter(
            KnowledgeUnit.kb_id == kb_id,
            KnowledgeUnit.import_id == import_id,
            KnowledgeUnit.status == KnowledgeUnitStatus.published,
        )
        .all()
    )
    for ku in kus:
        ku.status = KnowledgeUnitStatus.deprecated
        ku.deprecated_at = now
        index_builder.deprecate_entry(
            kb_id=kb_id,
            object_type=RetrievalObjectType.ku,
            object_id=ku.ku_id,
        )
    if kus:
        _inc(counts, "ku", len(kus))

    wikis = (
        db.query(Wiki)
        .filter(
            Wiki.kb_id == kb_id,
            Wiki.import_id == import_id,
            Wiki.status == WikiStatus.published,
        )
        .all()
    )
    for wiki in wikis:
        wiki.status = WikiStatus.deprecated
        wiki.deprecated_at = now
        index_builder.deprecate_entry(
            kb_id=kb_id,
            object_type=RetrievalObjectType.wiki,
            object_id=wiki.wiki_id,
        )
    if wikis:
        _inc(counts, "wiki", len(wikis))

    assets = (
        db.query(ManualAsset)
        .filter(
            ManualAsset.kb_id == kb_id,
            ManualAsset.import_id == import_id,
            ManualAsset.status == ManualAssetStatus.published,
        )
        .all()
    )
    for asset in assets:
        asset.status = ManualAssetStatus.deprecated
        asset.deprecated_at = now
        index_builder.deprecate_entry(
            kb_id=kb_id,
            object_type=RetrievalObjectType.manual_asset,
            object_id=asset.manual_asset_id,
        )
    if assets:
        _inc(counts, "manual_asset", len(assets))

    db.flush()
    return counts


def _detach_deprecated_asset_sources(db: Session, *, kb_id: UUID, import_id: UUID) -> None:
    for model in (KnowledgeUnit, Wiki):
        db.query(model).filter(
            model.kb_id == kb_id,
            model.import_id == import_id,
        ).update(
            {"source_doc_id": None, "source_node_id": None},
            synchronize_session=False,
        )
    db.query(KnowledgeUnit).filter(
        KnowledgeUnit.kb_id == kb_id,
        KnowledgeUnit.import_id == import_id,
    ).update({"bid_outline_id": None}, synchronize_session=False)
    db.query(ManualAsset).filter(
        ManualAsset.kb_id == kb_id,
        ManualAsset.import_id == import_id,
    ).update({"source_doc_id": None}, synchronize_session=False)
    db.flush()


def _delete_storage_dir(kb_id: UUID, import_id: UUID) -> bool:
    path = Path(Settings().storage_root) / str(kb_id) / str(import_id)
    if not path.exists():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return True


def _purge_template_for_import(db: Session, import_id: UUID, counts: dict[str, int]) -> None:
    templates = (
        db.query(Template)
        .filter(Template.source_import_id == import_id)
        .all()
    )
    template_ids = [row.template_id for row in templates]
    if not template_ids:
        return

    parse_task_ids = [
        row.parse_task_id
        for row in db.query(TemplateParseTask)
        .filter(TemplateParseTask.import_id == import_id)
        .all()
    ]

    if parse_task_ids:
        n = (
            db.query(TemplateParseSuggestion)
            .filter(TemplateParseSuggestion.parse_task_id.in_(parse_task_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "template_parse_suggestions", n)

        n = (
            db.query(TemplateStructureDiff)
            .filter(TemplateStructureDiff.parse_task_id.in_(parse_task_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "template_structure_diffs", n)

    n = (
        db.query(TemplateStructureDiff)
        .filter(TemplateStructureDiff.template_id.in_(template_ids))
        .delete(synchronize_session=False)
    )
    _inc(counts, "template_structure_diffs", n)

    chapter_ids = [
        row.template_chapter_id
        for row in db.query(TemplateChapter)
        .filter(TemplateChapter.template_id.in_(template_ids))
        .all()
    ]
    if chapter_ids:
        for model, key in (
            (TemplateMaterial, "template_materials"),
            (TemplateVariable, "template_variables"),
            (TemplateRule, "template_rules"),
        ):
            n = (
                db.query(model)
                .filter(model.template_id.in_(template_ids))
                .delete(synchronize_session=False)
            )
            _inc(counts, key, n)

        n = (
            db.query(TemplateChapter)
            .filter(TemplateChapter.template_id.in_(template_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "template_chapters", n)

    n = (
        db.query(TemplateParseTask)
        .filter(TemplateParseTask.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "template_parse_tasks", n)

    if template_ids:
        db.query(TemplateAuditLog).filter(TemplateAuditLog.template_id.in_(template_ids)).update(
            {"template_id": None},
            synchronize_session=False,
        )

    n = (
        db.query(Template)
        .filter(Template.source_import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "templates", n)


def _purge_actual_bid_for_import(db: Session, import_id: UUID, counts: dict[str, int]) -> None:
    parse_task_ids = [
        row.parse_task_id
        for row in db.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == import_id)
        .all()
    ]
    document_ids = [
        row.document_id for row in db.query(Document).filter(Document.import_id == import_id).all()
    ]
    outline_ids = [
        row.bid_outline_id
        for row in db.query(BidOutline).filter(BidOutline.import_id == import_id).all()
    ]

    if parse_task_ids:
        n = (
            db.query(DocumentParseSuggestion)
            .filter(DocumentParseSuggestion.parse_task_id.in_(parse_task_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "document_parse_suggestions", n)

        n = (
            db.query(BidOutlineStructureDiff)
            .filter(BidOutlineStructureDiff.parse_task_id.in_(parse_task_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "bid_outline_structure_diffs", n)

        n = (
            db.query(ActualBidParseTask)
            .filter(ActualBidParseTask.parse_task_id.in_(parse_task_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "actual_bid_parse_tasks", n)
        parse_task_ids = []

    if outline_ids:
        n = (
            db.query(BidOutlineNode)
            .filter(BidOutlineNode.bid_outline_id.in_(outline_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "bid_outline_nodes", n)

        n = (
            db.query(BidOutlineStructureDiff)
            .filter(BidOutlineStructureDiff.bid_outline_id.in_(outline_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "bid_outline_structure_diffs", n)

        n = (
            db.query(BidOutline)
            .filter(BidOutline.bid_outline_id.in_(outline_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "bid_outlines", n)

    if document_ids:
        n = (
            db.query(DocumentTreeNode)
            .filter(DocumentTreeNode.document_id.in_(document_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "document_tree_nodes", n)

        n = (
            db.query(Document)
            .filter(Document.document_id.in_(document_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "documents", n)


def _purge_import_core(
    db: Session,
    record: FileImport,
    counts: dict[str, int],
    *,
    deprecate_published: bool,
    deprecated_counts: dict[str, int],
) -> None:
    import_id = record.import_id
    kb_id = record.kb_id

    child_imports = (
        db.query(FileImport)
        .filter(FileImport.parent_import_id == import_id)
        .all()
    )
    for child in child_imports:
        if child.status == FileImportStatus.deleted:
            continue
        purge_file_import(
            db,
            kb_id=kb_id,
            import_id=child.import_id,
            operator_id="system",
            trace_id=None,
            deprecate_published=deprecate_published,
            _skip_child_check=True,
        )

    impact = check_purge_impact(db, kb_id=kb_id, import_id=import_id)
    if impact.has_published_assets:
        if not deprecate_published:
            raise FileImportPurgeServiceError(
                "Published knowledge assets exist; set deprecate_published=true to proceed",
                code="PUBLISHED_ASSETS_EXIST",
                status_code=409,
                details=impact.to_dict(),
            )
        merged = _deprecate_published_assets(db, kb_id=kb_id, import_id=import_id)
        for key, val in merged.items():
            _inc(deprecated_counts, key, val)

    _detach_deprecated_asset_sources(db, kb_id=kb_id, import_id=import_id)

    document_ids = [
        row.document_id for row in db.query(Document).filter(Document.import_id == import_id).all()
    ]
    if document_ids:
        n = (
            db.query(DocumentMediaAsset)
            .filter(DocumentMediaAsset.document_id.in_(document_ids))
            .delete(synchronize_session=False)
        )
        _inc(counts, "document_media_assets", n)

    n = (
        db.query(RetrievalIndexEntry)
        .filter(RetrievalIndexEntry.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "retrieval_index_entries", n)

    n = (
        db.query(CandidateKnowledge)
        .filter(CandidateKnowledge.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "candidate_knowledges", n)

    n = (
        db.query(CandidateKnowledgeStub)
        .filter(CandidateKnowledgeStub.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "candidate_knowledge_stubs", n)

    _purge_actual_bid_for_import(db, import_id, counts)
    _purge_template_for_import(db, import_id, counts)

    n = (
        db.query(TemplateMaterial)
        .filter(TemplateMaterial.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "template_materials", n)

    n = (
        db.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "downstream_task_entries", n)

    n = (
        db.query(ImportTask)
        .filter(ImportTask.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "import_tasks", n)

    n = (
        db.query(FilePurposeSuggestion)
        .filter(FilePurposeSuggestion.import_id == import_id)
        .delete(synchronize_session=False)
    )
    _inc(counts, "file_purpose_suggestions", n)

    n = (
        db.query(ClassificationReference)
        .filter(
            ClassificationReference.kb_id == kb_id,
            ClassificationReference.object_type == ReferenceObjectType.file_import,
            ClassificationReference.object_id == import_id,
        )
        .delete(synchronize_session=False)
    )
    _inc(counts, "classification_references", n)

    db.query(TemplateLibrary).filter(TemplateLibrary.source_import_id == import_id).update(
        {"source_import_id": None},
        synchronize_session=False,
    )
    db.query(TemplateAuditLog).filter(TemplateAuditLog.import_id == import_id).update(
        {"import_id": None},
        synchronize_session=False,
    )

    if _delete_storage_dir(kb_id, import_id):
        _inc(counts, "storage_dirs", 1)

    record.status = FileImportStatus.deleted
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    _inc(counts, "file_imports", 1)


def purge_file_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    operator_id: str,
    trace_id: UUID | None,
    deprecate_published: bool = False,
    _skip_child_check: bool = False,
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
    deprecated_counts: dict[str, int] = {}
    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.delete,
            payload_summary={
                "file_name": record.file_name,
                "status": record.status.value if record.status else None,
                "file_purpose": record.file_purpose.value if record.file_purpose else None,
                "deprecate_published": deprecate_published,
            },
        )
    )
    db.flush()

    _purge_import_core(
        db,
        record,
        counts,
        deprecate_published=deprecate_published,
        deprecated_counts=deprecated_counts,
    )
    db.flush()
    return PurgeSummary(
        import_id=str(import_id),
        file_name=record.file_name,
        deleted_counts=counts,
        deprecated_counts=deprecated_counts,
    )


def purge_all_file_imports(
    db: Session,
    *,
    kb_id: UUID,
    operator_id: str,
    trace_id: UUID | None,
) -> list[PurgeSummary]:
    roots = (
        db.query(FileImport)
        .filter(
            FileImport.kb_id == kb_id,
            FileImport.parent_import_id.is_(None),
            FileImport.status != FileImportStatus.deleted,
        )
        .order_by(FileImport.created_at.desc())
        .all()
    )
    summaries: list[PurgeSummary] = []
    for record in roots:
        if db.get(FileImport, record.import_id) is None:
            continue
        summaries.append(
            purge_file_import(
                db,
                kb_id=kb_id,
                import_id=record.import_id,
                operator_id=operator_id,
                trace_id=trace_id,
            )
        )

    purged_ids = {UUID(item.import_id) for item in summaries}
    orphans = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.status != FileImportStatus.deleted)
        .order_by(FileImport.created_at.desc())
        .all()
    )
    for record in orphans:
        if record.import_id in purged_ids or db.get(FileImport, record.import_id) is None:
            continue
        summaries.append(
            purge_file_import(
                db,
                kb_id=kb_id,
                import_id=record.import_id,
                operator_id=operator_id,
                trace_id=trace_id,
            )
        )
        purged_ids.add(record.import_id)

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
