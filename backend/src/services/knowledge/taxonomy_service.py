from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from src.models.knowledge_taxonomy import KnowledgeTaxonomy
from src.services.knowledge.taxonomy_field_utils import normalize_business_line_codes


class TaxonomyValidationError(ValueError):
    pass


def _base_query(db: Session):
    return db.query(KnowledgeTaxonomy).filter(
        KnowledgeTaxonomy.kb_id.is_(None),
        KnowledgeTaxonomy.is_active.is_(True),
    )


def list_taxonomy(
    db: Session,
    *,
    dimension: str | None = None,
    parent_code: str | None = None,
    active_only: bool = True,
) -> list[KnowledgeTaxonomy]:
    query = _base_query(db)
    if not active_only:
        query = db.query(KnowledgeTaxonomy).filter(KnowledgeTaxonomy.kb_id.is_(None))
    if dimension:
        query = query.filter(KnowledgeTaxonomy.dimension == dimension)
    if parent_code:
        query = query.filter(KnowledgeTaxonomy.parent_code == parent_code)
    return query.order_by(KnowledgeTaxonomy.sort_order, KnowledgeTaxonomy.code).all()


def _get_row(db: Session, *, dimension: str, code: str) -> KnowledgeTaxonomy | None:
    normalized = str(code or "").strip()
    if not normalized:
        return None
    return (
        _base_query(db)
        .filter(
            KnowledgeTaxonomy.dimension == dimension,
            KnowledgeTaxonomy.code == normalized,
        )
        .one_or_none()
    )


def validate_block_type_code(db: Session, code: str) -> str:
    normalized = str(code or "").strip()
    row = _get_row(db, dimension="block_type", code=normalized)
    if row is None:
        raise TaxonomyValidationError(f"invalid block_type_code: {code}")
    return normalized


def validate_application_type_code(db: Session, code: str) -> str:
    normalized = str(code or "").strip()
    row = _get_row(db, dimension="application_type", code=normalized)
    if row is None:
        raise TaxonomyValidationError(f"invalid application_type_code: {code}")
    return normalized


def validate_dynamic_type_code(db: Session, code: str) -> str:
    normalized = str(code or "").strip()
    row = _get_row(db, dimension="dynamic_type", code=normalized)
    if row is None:
        raise TaxonomyValidationError(f"invalid dynamic_type_code: {code}")
    return normalized


def validate_business_line_codes(db: Session, codes: list[str] | None) -> list[str]:
    normalized = normalize_business_line_codes(codes)
    for code in normalized:
        if _get_row(db, dimension="business_line", code=code) is None:
            raise TaxonomyValidationError(f"invalid business_line_code: {code}")
    return normalized


def get_taxonomy_label(db: Session, dimension: str, code: str) -> str | None:
    row = _get_row(db, dimension=dimension, code=code)
    return row.label if row else None


def expand_business_line_labels(db: Session, codes: Iterable[str]) -> list[str]:
    labels: list[str] = []
    for code in codes:
        label = get_taxonomy_label(db, "business_line", code)
        labels.append(label or str(code))
    return labels
