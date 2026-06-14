from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.classification_reference import (
    ClassificationReference,
    ClassificationType,
    ReferenceObjectType,
)
from src.models.file_import import (
    FileImport,
    FileImportStatus,
    FilePurpose,
    TargetObjectType,
)
from src.models.file_purpose_suggestion import FilePurposeSuggestion
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.models.product_category import CategoryStatus, ProductCategory
from src.services.actual_bid_parse_runner import enqueue_actual_bid_parse


class ConfirmServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_target_object_type(
    file_purpose: FilePurpose, explicit: TargetObjectType | None
) -> TargetObjectType:
    if explicit is not None:
        return explicit
    mapping = {
        FilePurpose.actual_bid: TargetObjectType.document,
        FilePurpose.template_file: TargetObjectType.document,
        FilePurpose.qualification: TargetObjectType.manual_asset,
        FilePurpose.ppt_material: TargetObjectType.template_material,
        FilePurpose.cover_guide: TargetObjectType.template_material,
        FilePurpose.writing_guide: TargetObjectType.template_material,
        FilePurpose.wiki_source: TargetObjectType.wiki,
        FilePurpose.other: TargetObjectType.ignored,
    }
    return mapping[file_purpose]


def _get_import_or_raise(db: Session, kb_id: UUID, import_id: UUID) -> FileImport:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise ConfirmServiceError(
            "File import not found", code="NOT_FOUND", status_code=404
        )
    return record


def _assert_can_change(record: FileImport, expected_version: int) -> None:
    if record.status != FileImportStatus.need_confirm:
        raise ConfirmServiceError(
            "Only need_confirm imports can be updated",
            code="INVALID_STATE",
            status_code=422,
        )
    if record.version != expected_version:
        raise ConfirmServiceError(
            "Version mismatch", code="CONFLICT", status_code=409
        )


def _validate_active_categories(
    db: Session, kb_id: UUID, category_ids: list[UUID]
) -> list[UUID]:
    valid_ids: list[UUID] = []
    for category_id in category_ids:
        category = db.get(ProductCategory, category_id)
        if (
            category is None
            or category.kb_id != kb_id
            or category.status != CategoryStatus.active
        ):
            raise ConfirmServiceError(
                f"Product category must be active: {category_id}",
                code="VALIDATION",
                status_code=422,
            )
        valid_ids.append(category_id)
    return valid_ids


def _validate_active_taxonomy(
    db: Session, kb_id: UUID, taxonomy_id: UUID | None
) -> UUID | None:
    if taxonomy_id is None:
        return None
    taxonomy = db.get(ChapterTaxonomy, taxonomy_id)
    if taxonomy is None or taxonomy.kb_id != kb_id or taxonomy.status != CategoryStatus.active:
        raise ConfirmServiceError(
            f"Chapter taxonomy must be active: {taxonomy_id}",
            code="VALIDATION",
            status_code=422,
        )
    return taxonomy_id


def _rewrite_classification_references(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    product_category_ids: list[UUID],
    chapter_taxonomy_id: UUID | None,
) -> None:
    (
        db.query(ClassificationReference)
        .filter(
            ClassificationReference.kb_id == kb_id,
            ClassificationReference.object_type == ReferenceObjectType.file_import,
            ClassificationReference.object_id == import_id,
        )
        .delete()
    )
    for category_id in product_category_ids:
        db.add(
            ClassificationReference(
                kb_id=kb_id,
                classification_type=ClassificationType.product_category,
                classification_id=category_id,
                object_type=ReferenceObjectType.file_import,
                object_id=import_id,
            )
        )
    if chapter_taxonomy_id is not None:
        db.add(
            ClassificationReference(
                kb_id=kb_id,
                classification_type=ClassificationType.chapter_taxonomy,
                classification_id=chapter_taxonomy_id,
                object_type=ReferenceObjectType.file_import,
                object_id=import_id,
            )
        )


def _detect_reference_source(
    db: Session,
    import_id: UUID,
    file_purpose: FilePurpose,
    product_category_ids: list[UUID],
    chapter_taxonomy_id: UUID | None,
) -> str:
    suggestion = (
        db.query(FilePurposeSuggestion)
        .filter(FilePurposeSuggestion.import_id == import_id)
        .one_or_none()
    )
    if suggestion is None:
        return "manual"
    if suggestion.suggested_purpose != file_purpose:
        return "manual"
    suggested_categories = set(suggestion.suggested_product_category_ids or [])
    if set(str(x) for x in product_category_ids) != suggested_categories:
        return "manual"
    suggested_taxonomy = (
        str(suggestion.suggested_chapter_taxonomy_id)
        if suggestion.suggested_chapter_taxonomy_id
        else None
    )
    if suggested_taxonomy != (str(chapter_taxonomy_id) if chapter_taxonomy_id else None):
        return "manual"
    return "suggested"


def _build_confirm_payload(record: FileImport) -> dict:
    return {
        "import_id": str(record.import_id),
        "status": record.status.value,
        "file_purpose": record.file_purpose.value if record.file_purpose else None,
        "product_category_ids": [str(x) for x in (record.product_category_ids or [])],
        "chapter_taxonomy_id": str(record.chapter_taxonomy_id)
        if record.chapter_taxonomy_id
        else None,
        "target_object_type": record.target_object_type.value
        if record.target_object_type
        else None,
        "enter_parsing": record.enter_parsing,
        "version": record.version,
        "confirmed_by": record.confirmed_by,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
    }


def _downstream_task_types(file_purpose: FilePurpose, enter_parsing: bool) -> list[DownstreamTaskType]:
    if not enter_parsing:
        return []
    mapping: dict[FilePurpose, list[DownstreamTaskType]] = {
        FilePurpose.template_file: [DownstreamTaskType.template_file_parse],
        FilePurpose.actual_bid: [
            DownstreamTaskType.document_parse,
            DownstreamTaskType.bid_outline_extract,
            DownstreamTaskType.candidate_knowledge_generate,
        ],
        FilePurpose.qualification: [DownstreamTaskType.manual_asset_candidate],
        FilePurpose.ppt_material: [DownstreamTaskType.template_material_ingest],
        FilePurpose.cover_guide: [DownstreamTaskType.template_material_ingest],
        FilePurpose.writing_guide: [DownstreamTaskType.template_material_ingest],
        FilePurpose.wiki_source: [DownstreamTaskType.wiki_candidate],
        FilePurpose.other: [],
    }
    return mapping[file_purpose]


def create_downstream_entries(
    db: Session,
    *,
    record: FileImport,
    operator_id: str,
    trace_id: UUID | None,
) -> list[dict]:
    created: list[dict] = []
    task_types = _downstream_task_types(record.file_purpose, bool(record.enter_parsing))
    if not task_types:
        return created

    existing = (
        db.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.import_id == record.import_id)
        .all()
    )
    existing_types = {item.task_type for item in existing}

    for task_type in task_types:
        if task_type in existing_types:
            continue
        entry = DownstreamTaskEntry(
            kb_id=record.kb_id,
            import_id=record.import_id,
            task_type=task_type,
            status=DownstreamTaskStatus.pending,
            payload={
                "file_purpose": record.file_purpose.value if record.file_purpose else None,
                "target_object_type": record.target_object_type.value
                if record.target_object_type
                else None,
            },
        )
        db.add(entry)
        db.flush()
        created.append(
            {
                "entry_id": str(entry.entry_id),
                "task_type": entry.task_type.value,
                "status": entry.status.value,
            }
        )

    if created:
        db.add(
            ImportAuditLog(
                trace_id=trace_id or uuid4(),
                kb_id=record.kb_id,
                import_id=record.import_id,
                operator_id=operator_id,
                action=ImportAuditAction.route,
                payload_summary={"entries": created},
            )
        )
    return created


def confirm_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    expected_version: int,
    file_purpose: FilePurpose,
    product_category_ids: list[UUID],
    chapter_taxonomy_id: UUID | None,
    enter_parsing: bool,
    target_object_type: TargetObjectType | None,
    operator_id: str,
    trace_id: UUID | None,
) -> dict:
    record = _get_import_or_raise(db, kb_id, import_id)
    _assert_can_change(record, expected_version)

    valid_category_ids = _validate_active_categories(db, kb_id, product_category_ids)
    valid_taxonomy_id = _validate_active_taxonomy(db, kb_id, chapter_taxonomy_id)
    resolved_target = _resolve_target_object_type(file_purpose, target_object_type)
    reference_source = _detect_reference_source(
        db,
        import_id,
        file_purpose,
        valid_category_ids,
        valid_taxonomy_id,
    )

    record.file_purpose = file_purpose
    record.product_category_ids = [str(x) for x in valid_category_ids]
    record.chapter_taxonomy_id = valid_taxonomy_id
    record.target_object_type = resolved_target
    record.enter_parsing = enter_parsing
    record.status = FileImportStatus.confirmed
    record.confirmed_by = operator_id
    record.confirmed_at = _now()
    record.version += 1

    _rewrite_classification_references(
        db,
        kb_id=kb_id,
        import_id=import_id,
        product_category_ids=valid_category_ids,
        chapter_taxonomy_id=valid_taxonomy_id,
    )
    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.confirm,
            payload_summary={
                "file_purpose": file_purpose.value,
                "product_category_ids": [str(x) for x in valid_category_ids],
                "chapter_taxonomy_id": str(valid_taxonomy_id)
                if valid_taxonomy_id
                else None,
                "target_object_type": resolved_target.value,
                "enter_parsing": enter_parsing,
                "reference_source": reference_source,
            },
        )
    )
    created_downstream_entries = create_downstream_entries(
        db,
        record=record,
        operator_id=operator_id,
        trace_id=trace_id,
    )
    actual_bid_parse_task_id: str | None = None
    if file_purpose == FilePurpose.actual_bid and enter_parsing:
        actual_bid_parse_task = enqueue_actual_bid_parse(
            db,
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            trace_id=trace_id,
        )
        actual_bid_parse_task_id = str(actual_bid_parse_task.parse_task_id)
    db.commit()
    db.refresh(record)
    payload = _build_confirm_payload(record)
    payload["downstream_entries_created"] = created_downstream_entries
    payload["actual_bid_parse_task_id"] = actual_bid_parse_task_id
    return payload


def ignore_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    expected_version: int,
    reason: str | None,
    operator_id: str,
    trace_id: UUID | None,
) -> dict:
    record = _get_import_or_raise(db, kb_id, import_id)
    _assert_can_change(record, expected_version)

    record.status = FileImportStatus.ignored
    record.target_object_type = TargetObjectType.ignored
    record.enter_parsing = False
    record.version += 1

    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.ignore,
            payload_summary={"reason": reason or ""},
        )
    )
    db.commit()
    db.refresh(record)
    return {
        "import_id": str(record.import_id),
        "status": record.status.value,
        "target_object_type": record.target_object_type.value
        if record.target_object_type
        else None,
        "enter_parsing": record.enter_parsing,
        "version": record.version,
    }
