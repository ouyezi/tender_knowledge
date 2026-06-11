from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.models.chapter_taxonomy import (
    ChapterTaxonomy,
    ChapterTaxonomyBinding,
    ChapterTaxonomySynonym,
)
from src.models.kb_clone_log import KBCloneLog
from src.models.product_category import ProductCategory, ProductCategoryAlias
from src.services.category_tree import build_path

MAX_NODES = 2000


def _clone_product_categories(
    db: Session, source_kb_id: UUID, target_kb_id: UUID
) -> dict[UUID, UUID]:
    categories = list(
        db.scalars(
            select(ProductCategory)
            .where(ProductCategory.kb_id == source_kb_id)
            .options(selectinload(ProductCategory.aliases))
            .order_by(ProductCategory.depth)
        ).all()
    )

    id_map: dict[UUID, UUID] = {}
    path_map: dict[UUID, str] = {}

    for cat in categories:
        new_id = uuid4()
        id_map[cat.category_id] = new_id
        parent_path = path_map.get(cat.parent_id) if cat.parent_id else None
        path = build_path(parent_path, str(new_id))
        path_map[new_id] = path

        db.add(
            ProductCategory(
                category_id=new_id,
                kb_id=target_kb_id,
                parent_id=id_map.get(cat.parent_id) if cat.parent_id else None,
                category_name=cat.category_name,
                category_code=cat.category_code,
                description=cat.description,
                status=cat.status,
                merged_into_id=None,
                path=path,
                depth=cat.depth,
            )
        )

    db.flush()

    for cat in categories:
        new_category_id = id_map[cat.category_id]
        for alias in cat.aliases:
            db.add(
                ProductCategoryAlias(
                    category_id=new_category_id,
                    kb_id=target_kb_id,
                    alias=alias.alias,
                    alias_normalized=alias.alias_normalized,
                )
            )

    return id_map


def _clone_chapter_taxonomies(
    db: Session,
    source_kb_id: UUID,
    target_kb_id: UUID,
    category_id_map: dict[UUID, UUID],
) -> None:
    taxonomies = list(
        db.scalars(
            select(ChapterTaxonomy)
            .where(ChapterTaxonomy.kb_id == source_kb_id)
            .options(
                selectinload(ChapterTaxonomy.synonyms),
                selectinload(ChapterTaxonomy.bindings),
            )
            .order_by(ChapterTaxonomy.depth)
        ).all()
    )

    tax_id_map: dict[UUID, UUID] = {}
    path_map: dict[UUID, str] = {}

    for tax in taxonomies:
        new_id = uuid4()
        tax_id_map[tax.taxonomy_id] = new_id
        parent_path = path_map.get(tax.parent_id) if tax.parent_id else None
        path = build_path(parent_path, str(new_id))
        path_map[new_id] = path

        db.add(
            ChapterTaxonomy(
                taxonomy_id=new_id,
                kb_id=target_kb_id,
                parent_id=tax_id_map.get(tax.parent_id) if tax.parent_id else None,
                standard_name=tax.standard_name,
                taxonomy_code=tax.taxonomy_code,
                description=tax.description,
                status=tax.status,
                merged_into_id=None,
                path=path,
                depth=tax.depth,
            )
        )

    db.flush()

    for tax in taxonomies:
        new_taxonomy_id = tax_id_map[tax.taxonomy_id]
        for syn in tax.synonyms:
            db.add(
                ChapterTaxonomySynonym(
                    taxonomy_id=new_taxonomy_id,
                    kb_id=target_kb_id,
                    synonym=syn.synonym,
                    synonym_normalized=syn.synonym_normalized,
                )
            )
        for binding in tax.bindings:
            mapped_category_id = category_id_map.get(binding.category_id)
            if mapped_category_id is None:
                continue
            db.add(
                ChapterTaxonomyBinding(
                    kb_id=target_kb_id,
                    taxonomy_id=new_taxonomy_id,
                    category_id=mapped_category_id,
                    source=binding.source,
                    created_by=binding.created_by,
                )
            )


def clone_kb(
    db: Session,
    source_kb_id: UUID,
    target_kb_id: UUID,
    *,
    operator_id: str,
    trace_id: str,
) -> None:
    """Deep-clone classification trees from source to target KB."""
    categories = list(
        db.scalars(
            select(ProductCategory).where(ProductCategory.kb_id == source_kb_id)
        ).all()
    )
    taxonomies = list(
        db.scalars(
            select(ChapterTaxonomy).where(ChapterTaxonomy.kb_id == source_kb_id)
        ).all()
    )
    if len(categories) + len(taxonomies) > MAX_NODES:
        raise ValueError(f"Clone exceeds MAX_NODES ({MAX_NODES})")

    category_id_map = _clone_product_categories(db, source_kb_id, target_kb_id)
    _clone_chapter_taxonomies(db, source_kb_id, target_kb_id, category_id_map)

    log = KBCloneLog(
        target_kb_id=target_kb_id,
        source_kb_id=source_kb_id,
        operator_id=operator_id,
        trace_id=trace_id,
    )
    db.add(log)
    db.commit()
