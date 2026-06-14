from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.product_category import CategoryStatus, ProductCategory


class PublishValidationError(Exception):
    def __init__(self, message: str, *, code: str = "PUBLISH_VALIDATION_FAILED") -> None:
        self.code = code
        super().__init__(message)


def _require(value, field_name: str) -> None:
    if value is None:
        raise PublishValidationError(f"{field_name} is required")
    if isinstance(value, str) and not value.strip():
        raise PublishValidationError(f"{field_name} is required")


def _as_uuid(raw: str | UUID | None, field_name: str) -> UUID | None:
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(raw)
    except ValueError as exc:
        raise PublishValidationError(f"{field_name} must be uuid") from exc


def _validate_taxonomy(db: Session | None, *, kb_id: UUID, taxonomy_id: UUID | None) -> None:
    if taxonomy_id is None or db is None:
        return
    taxonomy = (
        db.query(ChapterTaxonomy)
        .filter(ChapterTaxonomy.kb_id == kb_id)
        .filter(ChapterTaxonomy.taxonomy_id == taxonomy_id)
        .one_or_none()
    )
    if taxonomy is None:
        raise PublishValidationError("chapter_taxonomy_id is invalid")
    if taxonomy.status != CategoryStatus.active:
        raise PublishValidationError(
            "chapter_taxonomy_id is deprecated",
            code="DEPRECATED_TAXONOMY",
        )


def _validate_categories(db: Session | None, *, kb_id: UUID, category_ids: list[UUID]) -> None:
    if not category_ids or db is None:
        return
    rows = (
        db.query(ProductCategory)
        .filter(ProductCategory.kb_id == kb_id)
        .filter(ProductCategory.category_id.in_(category_ids))
        .all()
    )
    if len(rows) != len(set(category_ids)):
        raise PublishValidationError("product_category_ids contains invalid category")
    if any(row.status != CategoryStatus.active for row in rows):
        raise PublishValidationError("product_category_ids contains inactive category")


def validate_publish(
    *,
    db: Session | None,
    kb_id: UUID,
    confirm_as: str,
    payload: dict,
    view,
) -> None:
    if confirm_as not in {
        "ku",
        "wiki",
        "template_chapter",
        "manual_asset",
        "chapter_pattern",
        "product_category",
        "ignore",
    }:
        raise PublishValidationError("confirm_as is invalid")

    title = payload.get("title") or view.title
    content = payload.get("content")
    if content is None:
        content = getattr(view, "content", None)

    knowledge_type = payload.get("knowledge_type") or getattr(
        view, "suggested_knowledge_type", None
    )
    taxonomy_id = _as_uuid(payload.get("chapter_taxonomy_id"), "chapter_taxonomy_id")
    raw_categories = payload.get("product_category_ids")
    category_ids = [] if raw_categories is None else [_as_uuid(x, "product_category_ids") for x in raw_categories]
    category_ids = [x for x in category_ids if x is not None]

    if confirm_as == "ku":
        _require(knowledge_type, "knowledge_type")
        _require(title, "title")
        _require(content, "content")
        if view.channel == "document":
            if not view.source_trace.get("source_doc_id"):
                raise PublishValidationError("source_doc_id is required for document candidate")
            if not view.source_trace.get("source_node_id"):
                raise PublishValidationError("source_node_id is required for document candidate")
    elif confirm_as == "wiki":
        _require(title, "title")
        _require(content, "content")
    elif confirm_as == "template_chapter":
        _require(title, "title")
        template_id = payload.get("template_id") or view.source_trace.get("template_id")
        _require(template_id, "template_id")
        if view.channel != "template":
            raise PublishValidationError("template_chapter only supports template channel")
    elif confirm_as == "manual_asset":
        _require(title, "title")
        _require(payload.get("asset_type"), "asset_type")
    elif confirm_as == "chapter_pattern":
        _require(title, "title")
    elif confirm_as == "product_category":
        _require(title, "title")
    else:
        # ignore has no extra required fields
        return

    _validate_taxonomy(db, kb_id=kb_id, taxonomy_id=taxonomy_id)
    _validate_categories(db, kb_id=kb_id, category_ids=category_ids)
