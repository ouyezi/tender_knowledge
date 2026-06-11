import re
import unicodedata
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.chapter_taxonomy import ChapterTaxonomy, ChapterTaxonomySynonym
from src.models.product_category import ProductCategory, ProductCategoryAlias


class AliasConflictError(Exception):
    def __init__(self, message: str, *, field: str, value: str):
        self.field = field
        self.value = value
        super().__init__(message)


def normalize(name: str) -> str:
    text = unicodedata.normalize("NFKC", name.strip())
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def filter_extra_names(canonical: str, names: list[str]) -> list[str]:
    """Drop blanks, duplicates, and entries equivalent to the canonical name."""
    norm_canonical = normalize(canonical)
    seen = {norm_canonical}
    filtered: list[str] = []
    for name in names:
        if not name or not name.strip():
            continue
        norm = normalize(name)
        if norm in seen:
            continue
        seen.add(norm)
        filtered.append(name.strip())
    return filtered


def check_unique(
    db: Session,
    kb_id: UUID,
    names: list[str],
    *,
    exclude_category_id: UUID | None = None,
) -> None:
    cleaned = [n for n in names if n and n.strip()]
    normalized = [normalize(n) for n in cleaned]
    if not normalized:
        return

    if len(normalized) != len(set(normalized)):
        dup = next(n for n in normalized if normalized.count(n) > 1)
        raise AliasConflictError(
            f"Duplicate alias in request: {dup}",
            field="alias",
            value=dup,
        )

    for norm, original in zip(normalized, cleaned):
        cat_stmt = select(ProductCategory).where(ProductCategory.kb_id == kb_id)
        if exclude_category_id is not None:
            cat_stmt = cat_stmt.where(ProductCategory.category_id != exclude_category_id)
        for row in db.scalars(cat_stmt).all():
            if normalize(row.category_name) == norm:
                raise AliasConflictError(
                    f"Name conflicts with category: {row.category_name}",
                    field="alias",
                    value=original,
                )

        alias_stmt = select(ProductCategoryAlias).where(
            ProductCategoryAlias.kb_id == kb_id,
            ProductCategoryAlias.alias_normalized == norm,
        )
        if exclude_category_id is not None:
            alias_stmt = alias_stmt.where(
                ProductCategoryAlias.category_id != exclude_category_id
            )
        if db.scalar(alias_stmt) is not None:
            raise AliasConflictError(
                f"Alias already exists: {original}",
                field="alias",
                value=original,
            )


def check_taxonomy_unique(
    db: Session,
    kb_id: UUID,
    names: list[str],
    *,
    exclude_taxonomy_id: UUID | None = None,
) -> None:
    cleaned = [n for n in names if n and n.strip()]
    normalized = [normalize(n) for n in cleaned]
    if not normalized:
        return

    if len(normalized) != len(set(normalized)):
        dup = next(n for n in normalized if normalized.count(n) > 1)
        raise AliasConflictError(
            f"Duplicate synonym in request: {dup}",
            field="synonym",
            value=dup,
        )

    for norm, original in zip(normalized, cleaned):
        tax_stmt = select(ChapterTaxonomy).where(ChapterTaxonomy.kb_id == kb_id)
        if exclude_taxonomy_id is not None:
            tax_stmt = tax_stmt.where(ChapterTaxonomy.taxonomy_id != exclude_taxonomy_id)
        for row in db.scalars(tax_stmt).all():
            if normalize(row.standard_name) == norm:
                raise AliasConflictError(
                    f"Name conflicts with taxonomy: {row.standard_name}",
                    field="synonym",
                    value=original,
                )

        syn_stmt = select(ChapterTaxonomySynonym).where(
            ChapterTaxonomySynonym.kb_id == kb_id,
            ChapterTaxonomySynonym.synonym_normalized == norm,
        )
        if exclude_taxonomy_id is not None:
            syn_stmt = syn_stmt.where(
                ChapterTaxonomySynonym.taxonomy_id != exclude_taxonomy_id
            )
        if db.scalar(syn_stmt) is not None:
            raise AliasConflictError(
                f"Synonym already exists: {original}",
                field="synonym",
                value=original,
            )
