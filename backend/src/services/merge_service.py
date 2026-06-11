from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.audit_log import AuditAction, AuditEntityType
from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.classification_reference import ClassificationReference, ClassificationType
from src.models.product_category import CategoryStatus, ProductCategory
from src.services.audit_service import log_classification_audit


class MergeError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _has_active_children(db: Session, entity_id: UUID, *, model, id_column) -> bool:
    return (
        db.scalar(
            select(id_column).where(
                model.parent_id == entity_id,
                model.status == CategoryStatus.active,
            )
        )
        is not None
    )


def has_active_product_children(db: Session, category_id: UUID) -> bool:
    return _has_active_children(
        db, category_id, model=ProductCategory, id_column=ProductCategory.category_id
    )


def has_active_taxonomy_children(db: Session, taxonomy_id: UUID) -> bool:
    return _has_active_children(
        db, taxonomy_id, model=ChapterTaxonomy, id_column=ChapterTaxonomy.taxonomy_id
    )


def is_ancestor(ancestor_id: UUID, descendant_path: str) -> bool:
    return f"/{ancestor_id}/" in descendant_path


def migrate_references(
    db: Session,
    kb_id: UUID,
    classification_type: ClassificationType,
    source_id: UUID,
    target_id: UUID,
) -> int:
    refs = list(
        db.scalars(
            select(ClassificationReference).where(
                ClassificationReference.kb_id == kb_id,
                ClassificationReference.classification_type == classification_type,
                ClassificationReference.classification_id == source_id,
            )
        ).all()
    )
    migrated = 0
    for ref in refs:
        duplicate = db.scalar(
            select(ClassificationReference.reference_id).where(
                ClassificationReference.kb_id == kb_id,
                ClassificationReference.classification_type == classification_type,
                ClassificationReference.classification_id == target_id,
                ClassificationReference.object_type == ref.object_type,
                ClassificationReference.object_id == ref.object_id,
            )
        )
        if duplicate is not None:
            db.delete(ref)
        else:
            ref.classification_id = target_id
            migrated += 1
    return migrated


def merge_product_category(
    db: Session,
    source: ProductCategory,
    target: ProductCategory,
    *,
    operator_id: str | None = None,
    trace_id=None,
) -> dict:
    if source.category_id == target.category_id:
        raise MergeError("VALIDATION", "Source and target must differ")
    if source.kb_id != target.kb_id:
        raise MergeError("VALIDATION", "Source and target must be in same KB")
    if has_active_product_children(db, source.category_id):
        raise MergeError("HAS_CHILDREN", "Source category has child nodes")
    if is_ancestor(source.category_id, target.path) or is_ancestor(
        target.category_id, source.path
    ):
        raise MergeError("ANCESTOR_RELATION", "Cannot merge ancestor and descendant")

    migrated_count = migrate_references(
        db,
        source.kb_id,
        ClassificationType.product_category,
        source.category_id,
        target.category_id,
    )
    source.status = CategoryStatus.merged
    source.merged_into_id = target.category_id

    log_classification_audit(
        db,
        kb_id=source.kb_id,
        entity_type=AuditEntityType.product_category,
        entity_id=source.category_id,
        action=AuditAction.merge,
        payload_summary={
            "source_id": str(source.category_id),
            "target_id": str(target.category_id),
            "migrated_reference_count": migrated_count,
        },
        operator_id=operator_id,
        trace_id=trace_id,
    )
    db.commit()
    db.refresh(source)
    return {
        "source_id": str(source.category_id),
        "target_id": str(target.category_id),
        "migrated_reference_count": migrated_count,
    }


def merge_chapter_taxonomy(
    db: Session,
    source: ChapterTaxonomy,
    target: ChapterTaxonomy,
    *,
    operator_id: str | None = None,
    trace_id=None,
) -> dict:
    if source.taxonomy_id == target.taxonomy_id:
        raise MergeError("VALIDATION", "Source and target must differ")
    if source.kb_id != target.kb_id:
        raise MergeError("VALIDATION", "Source and target must be in same KB")
    if has_active_taxonomy_children(db, source.taxonomy_id):
        raise MergeError("HAS_CHILDREN", "Source taxonomy has child nodes")
    if is_ancestor(source.taxonomy_id, target.path) or is_ancestor(
        target.taxonomy_id, source.path
    ):
        raise MergeError("ANCESTOR_RELATION", "Cannot merge ancestor and descendant")

    migrated_count = migrate_references(
        db,
        source.kb_id,
        ClassificationType.chapter_taxonomy,
        source.taxonomy_id,
        target.taxonomy_id,
    )
    source.status = CategoryStatus.merged
    source.merged_into_id = target.taxonomy_id

    log_classification_audit(
        db,
        kb_id=source.kb_id,
        entity_type=AuditEntityType.chapter_taxonomy,
        entity_id=source.taxonomy_id,
        action=AuditAction.merge,
        payload_summary={
            "source_id": str(source.taxonomy_id),
            "target_id": str(target.taxonomy_id),
            "migrated_reference_count": migrated_count,
        },
        operator_id=operator_id,
        trace_id=trace_id,
    )
    db.commit()
    db.refresh(source)
    return {
        "source_id": str(source.taxonomy_id),
        "target_id": str(target.taxonomy_id),
        "migrated_reference_count": migrated_count,
    }
