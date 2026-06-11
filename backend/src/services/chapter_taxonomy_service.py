from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models.chapter_taxonomy import (
    BindingSource,
    ChapterTaxonomy,
    ChapterTaxonomyBinding,
    ChapterTaxonomySynonym,
)
from src.models.product_category import CategoryStatus, ProductCategory
from src.models.audit_log import AuditAction, AuditEntityType
from src.services import alias_registry
from src.services.alias_registry import AliasConflictError, normalize
from src.services.audit_service import log_classification_audit
from src.services.category_tree import assert_no_cycle, build_path
from src.services.product_category_service import InvalidStateError, ValidationError

MAX_DEPTH = 10


def _sibling_code_exists(
    db: Session,
    kb_id: UUID,
    parent_id: UUID | None,
    taxonomy_code: str,
    *,
    exclude_id: UUID | None = None,
) -> bool:
    stmt = select(ChapterTaxonomy).where(
        ChapterTaxonomy.kb_id == kb_id,
        ChapterTaxonomy.parent_id == parent_id,
        ChapterTaxonomy.taxonomy_code == taxonomy_code,
    )
    if exclude_id is not None:
        stmt = stmt.where(ChapterTaxonomy.taxonomy_id != exclude_id)
    return db.scalar(stmt) is not None


def _add_synonyms(
    db: Session,
    taxonomy: ChapterTaxonomy,
    synonyms: list[str],
) -> None:
    for text in synonyms:
        if not text or not text.strip():
            continue
        db.add(
            ChapterTaxonomySynonym(
                taxonomy_id=taxonomy.taxonomy_id,
                kb_id=taxonomy.kb_id,
                synonym=text.strip(),
                synonym_normalized=normalize(text),
            )
        )


def _validate_category_ids(
    db: Session, kb_id: UUID, category_ids: list[UUID]
) -> None:
    for cid in category_ids:
        cat = db.get(ProductCategory, cid)
        if cat is None or cat.kb_id != kb_id:
            raise ValidationError(f"Product category not found: {cid}")
        if cat.status != CategoryStatus.active:
            raise ValidationError(f"Product category must be active: {cid}")


def _set_bindings(
    db: Session,
    taxonomy: ChapterTaxonomy,
    category_ids: list[UUID],
    *,
    source: BindingSource,
    operator_id: str,
) -> None:
    _validate_category_ids(db, taxonomy.kb_id, category_ids)
    for existing in list(taxonomy.bindings):
        db.delete(existing)
    db.flush()
    for cid in category_ids:
        db.add(
            ChapterTaxonomyBinding(
                kb_id=taxonomy.kb_id,
                taxonomy_id=taxonomy.taxonomy_id,
                category_id=cid,
                source=source,
                created_by=operator_id,
            )
        )


def create_taxonomy(
    db: Session,
    kb_id: UUID,
    *,
    standard_name: str,
    taxonomy_code: str,
    parent_id: UUID | None = None,
    description: str | None = None,
    synonyms: list[str] | None = None,
    product_category_ids: list[UUID] | None = None,
    operator_id: str = "system",
) -> ChapterTaxonomy:
    synonym_list = alias_registry.filter_extra_names(standard_name, synonyms or [])
    alias_registry.check_taxonomy_unique(db, kb_id, [standard_name, *synonym_list])

    parent: ChapterTaxonomy | None = None
    parent_path: str | None = None
    depth = 0
    if parent_id is not None:
        parent = db.get(ChapterTaxonomy, parent_id)
        if parent is None or parent.kb_id != kb_id:
            raise ValidationError("Parent taxonomy not found")
        if parent.status != CategoryStatus.active:
            raise ValidationError("Parent taxonomy must be active")
        parent_path = parent.path
        depth = parent.depth + 1
        if depth > MAX_DEPTH:
            raise ValidationError(f"Depth exceeds maximum of {MAX_DEPTH}")

    if _sibling_code_exists(db, kb_id, parent_id, taxonomy_code):
        raise AliasConflictError(
            f"Taxonomy code already exists: {taxonomy_code}",
            field="taxonomy_code",
            value=taxonomy_code,
        )

    taxonomy_id = uuid4()
    path = build_path(parent_path, str(taxonomy_id))
    assert_no_cycle(parent_path, str(taxonomy_id))

    taxonomy = ChapterTaxonomy(
        taxonomy_id=taxonomy_id,
        kb_id=kb_id,
        parent_id=parent_id,
        standard_name=standard_name,
        taxonomy_code=taxonomy_code,
        description=description,
        path=path,
        depth=depth,
        status=CategoryStatus.active,
    )
    db.add(taxonomy)
    db.flush()
    _add_synonyms(db, taxonomy, synonym_list)
    if product_category_ids:
        _set_bindings(
            db,
            taxonomy,
            product_category_ids,
            source=BindingSource.manual,
            operator_id=operator_id,
        )
    log_classification_audit(
        db,
        kb_id=kb_id,
        entity_type=AuditEntityType.chapter_taxonomy,
        entity_id=taxonomy.taxonomy_id,
        action=AuditAction.create,
        payload_summary={
            "standard_name": standard_name,
            "taxonomy_code": taxonomy_code,
        },
    )
    db.commit()
    db.refresh(taxonomy)
    return taxonomy


def list_taxonomies(
    db: Session,
    kb_id: UUID,
    *,
    status: CategoryStatus | None = CategoryStatus.active,
    include_inactive: bool = False,
    product_category_id: UUID | None = None,
) -> list[ChapterTaxonomy]:
    stmt = select(ChapterTaxonomy).where(ChapterTaxonomy.kb_id == kb_id)
    if not include_inactive and status is not None:
        stmt = stmt.where(ChapterTaxonomy.status == status)
    if product_category_id is not None:
        stmt = stmt.where(
            ChapterTaxonomy.taxonomy_id.in_(
                select(ChapterTaxonomyBinding.taxonomy_id).where(
                    ChapterTaxonomyBinding.kb_id == kb_id,
                    ChapterTaxonomyBinding.category_id == product_category_id,
                )
            )
        )
    return list(db.scalars(stmt.order_by(ChapterTaxonomy.path)).all())


def build_tree_nodes(taxonomies: list[ChapterTaxonomy]) -> list[dict]:
    by_id: dict[UUID, dict] = {}
    roots: list[dict] = []

    for tax in taxonomies:
        node = {
            "taxonomy_id": str(tax.taxonomy_id),
            "parent_id": str(tax.parent_id) if tax.parent_id else None,
            "standard_name": tax.standard_name,
            "taxonomy_code": tax.taxonomy_code,
            "synonyms": [s.synonym for s in tax.synonyms],
            "description": tax.description or "",
            "status": tax.status.value,
            "depth": tax.depth,
            "children": [],
        }
        by_id[tax.taxonomy_id] = node

    for tax in taxonomies:
        node = by_id[tax.taxonomy_id]
        if tax.parent_id and tax.parent_id in by_id:
            by_id[tax.parent_id]["children"].append(node)
        else:
            roots.append(node)

    return roots


def get_taxonomy(
    db: Session, kb_id: UUID, taxonomy_id: UUID
) -> ChapterTaxonomy | None:
    tax = db.get(ChapterTaxonomy, taxonomy_id)
    if tax is None or tax.kb_id != kb_id:
        return None
    return tax


def get_taxonomy_detail(
    db: Session, kb_id: UUID, taxonomy_id: UUID
) -> dict | None:
    tax = get_taxonomy(db, kb_id, taxonomy_id)
    if tax is None:
        return None

    child_ids = list(
        db.scalars(
            select(ChapterTaxonomy.taxonomy_id).where(
                ChapterTaxonomy.parent_id == taxonomy_id,
                ChapterTaxonomy.kb_id == kb_id,
            )
        ).all()
    )

    breadcrumb: list[dict] = []
    if tax.path:
        for pid in [p for p in tax.path.strip("/").split("/") if p]:
            ancestor = db.get(ChapterTaxonomy, UUID(pid))
            if ancestor:
                breadcrumb.append(
                    {
                        "taxonomy_id": str(ancestor.taxonomy_id),
                        "standard_name": ancestor.standard_name,
                    }
                )

    return {
        "taxonomy_id": str(tax.taxonomy_id),
        "parent_id": str(tax.parent_id) if tax.parent_id else None,
        "standard_name": tax.standard_name,
        "taxonomy_code": tax.taxonomy_code,
        "description": tax.description or "",
        "status": tax.status.value,
        "depth": tax.depth,
        "synonyms": [s.synonym for s in tax.synonyms],
        "product_category_ids": [str(b.category_id) for b in tax.bindings],
        "child_ids": [str(cid) for cid in child_ids],
        "breadcrumb": breadcrumb,
        "created_at": tax.created_at.isoformat(),
        "updated_at": tax.updated_at.isoformat(),
    }


def update_taxonomy(
    db: Session,
    taxonomy: ChapterTaxonomy,
    *,
    standard_name: str | None = None,
    description: str | None = None,
    status: CategoryStatus | None = None,
) -> ChapterTaxonomy:
    if standard_name is not None:
        alias_registry.check_taxonomy_unique(
            db,
            taxonomy.kb_id,
            [standard_name],
            exclude_taxonomy_id=taxonomy.taxonomy_id,
        )
        taxonomy.standard_name = standard_name
    if description is not None:
        taxonomy.description = description
    if status is not None:
        if taxonomy.status == CategoryStatus.merged:
            raise InvalidStateError("Cannot change status of merged taxonomy")
        taxonomy.status = status
    log_classification_audit(
        db,
        kb_id=taxonomy.kb_id,
        entity_type=AuditEntityType.chapter_taxonomy,
        entity_id=taxonomy.taxonomy_id,
        action=AuditAction.update,
        payload_summary={
            "standard_name": standard_name,
            "description": description,
            "status": status.value if status else None,
        },
    )
    db.commit()
    db.refresh(taxonomy)
    return taxonomy


def replace_synonyms(
    db: Session,
    taxonomy: ChapterTaxonomy,
    synonyms: list[str],
) -> ChapterTaxonomy:
    synonym_list = alias_registry.filter_extra_names(taxonomy.standard_name, synonyms)
    alias_registry.check_taxonomy_unique(
        db,
        taxonomy.kb_id,
        [taxonomy.standard_name, *synonym_list],
        exclude_taxonomy_id=taxonomy.taxonomy_id,
    )
    for existing in list(taxonomy.synonyms):
        db.delete(existing)
    db.flush()
    _add_synonyms(db, taxonomy, synonym_list)
    log_classification_audit(
        db,
        kb_id=taxonomy.kb_id,
        entity_type=AuditEntityType.chapter_taxonomy,
        entity_id=taxonomy.taxonomy_id,
        action=AuditAction.update,
        payload_summary={"synonyms": synonym_list},
    )
    db.commit()
    db.refresh(taxonomy)
    return taxonomy


def replace_product_category_bindings(
    db: Session,
    taxonomy: ChapterTaxonomy,
    category_ids: list[UUID],
    *,
    source: BindingSource = BindingSource.manual,
    operator_id: str = "system",
) -> ChapterTaxonomy:
    _set_bindings(db, taxonomy, category_ids, source=source, operator_id=operator_id)
    log_classification_audit(
        db,
        kb_id=taxonomy.kb_id,
        entity_type=AuditEntityType.chapter_taxonomy,
        entity_id=taxonomy.taxonomy_id,
        action=AuditAction.bind,
        payload_summary={"product_category_ids": [str(c) for c in category_ids]},
    )
    db.commit()
    db.refresh(taxonomy)
    return taxonomy


def search_taxonomies(
    db: Session,
    kb_id: UUID,
    *,
    q: str,
    limit: int = 20,
    status: CategoryStatus = CategoryStatus.active,
    product_category_id: UUID | None = None,
) -> list[dict]:
    norm_q = normalize(q)
    pattern = f"%{q}%"
    stmt = select(ChapterTaxonomy).where(
        ChapterTaxonomy.kb_id == kb_id,
        ChapterTaxonomy.status == status,
        or_(
            ChapterTaxonomy.standard_name.ilike(pattern),
            ChapterTaxonomy.taxonomy_id.in_(
                select(ChapterTaxonomySynonym.taxonomy_id).where(
                    ChapterTaxonomySynonym.kb_id == kb_id,
                    ChapterTaxonomySynonym.synonym_normalized.contains(norm_q),
                )
            ),
        ),
    )
    if product_category_id is not None:
        stmt = stmt.where(
            ChapterTaxonomy.taxonomy_id.in_(
                select(ChapterTaxonomyBinding.taxonomy_id).where(
                    ChapterTaxonomyBinding.kb_id == kb_id,
                    ChapterTaxonomyBinding.category_id == product_category_id,
                )
            )
        )
    stmt = stmt.limit(limit)

    results: list[dict] = []
    for tax in db.scalars(stmt).all():
        matched_synonym = None
        for syn in tax.synonyms:
            if norm_q in syn.synonym_normalized:
                matched_synonym = syn.synonym
                break
        path_labels = []
        for pid in tax.path.strip("/").split("/"):
            if not pid:
                continue
            ancestor = db.get(ChapterTaxonomy, UUID(pid))
            if ancestor:
                path_labels.append(ancestor.standard_name)
        results.append(
            {
                "taxonomy_id": str(tax.taxonomy_id),
                "standard_name": tax.standard_name,
                "matched_synonym": matched_synonym,
                "path_labels": path_labels,
            }
        )
    return results


def deactivate_taxonomy(db: Session, taxonomy: ChapterTaxonomy) -> ChapterTaxonomy:
    active_children = db.scalar(
        select(ChapterTaxonomy.taxonomy_id).where(
            ChapterTaxonomy.parent_id == taxonomy.taxonomy_id,
            ChapterTaxonomy.status == CategoryStatus.active,
        )
    )
    if active_children is not None:
        raise InvalidStateError(
            "Taxonomy has active children", code="HAS_ACTIVE_CHILDREN"
        )
    taxonomy.status = CategoryStatus.inactive
    log_classification_audit(
        db,
        kb_id=taxonomy.kb_id,
        entity_type=AuditEntityType.chapter_taxonomy,
        entity_id=taxonomy.taxonomy_id,
        action=AuditAction.deactivate,
    )
    db.commit()
    db.refresh(taxonomy)
    return taxonomy


def archive_taxonomy(db: Session, taxonomy: ChapterTaxonomy) -> ChapterTaxonomy:
    taxonomy.status = CategoryStatus.archived
    log_classification_audit(
        db,
        kb_id=taxonomy.kb_id,
        entity_type=AuditEntityType.chapter_taxonomy,
        entity_id=taxonomy.taxonomy_id,
        action=AuditAction.archive,
    )
    db.commit()
    db.refresh(taxonomy)
    return taxonomy
