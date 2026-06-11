from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models.product_category import (
    CategoryStatus,
    ProductCategory,
    ProductCategoryAlias,
)
from src.models.audit_log import AuditAction, AuditEntityType
from src.services import alias_registry
from src.services.alias_registry import AliasConflictError, normalize
from src.services.audit_service import log_classification_audit
from src.services.category_tree import assert_no_cycle, build_path

MAX_DEPTH = 10


class ValidationError(Exception):
    def __init__(self, message: str, *, code: str = "VALIDATION"):
        self.code = code
        super().__init__(message)


class InvalidStateError(Exception):
    def __init__(self, message: str, *, code: str = "INVALID_STATE"):
        self.code = code
        super().__init__(message)


def _sibling_code_exists(
    db: Session,
    kb_id: UUID,
    parent_id: UUID | None,
    category_code: str,
    *,
    exclude_id: UUID | None = None,
) -> bool:
    stmt = select(ProductCategory).where(
        ProductCategory.kb_id == kb_id,
        ProductCategory.parent_id == parent_id,
        ProductCategory.category_code == category_code,
    )
    if exclude_id is not None:
        stmt = stmt.where(ProductCategory.category_id != exclude_id)
    return db.scalar(stmt) is not None


def _add_aliases(
    db: Session,
    category: ProductCategory,
    aliases: list[str],
) -> None:
    for alias_text in aliases:
        if not alias_text or not alias_text.strip():
            continue
        db.add(
            ProductCategoryAlias(
                category_id=category.category_id,
                kb_id=category.kb_id,
                alias=alias_text.strip(),
                alias_normalized=normalize(alias_text),
            )
        )


def create_category(
    db: Session,
    kb_id: UUID,
    *,
    category_name: str,
    category_code: str,
    parent_id: UUID | None = None,
    description: str | None = None,
    aliases: list[str] | None = None,
) -> ProductCategory:
    alias_list = alias_registry.filter_extra_names(category_name, aliases or [])
    alias_registry.check_unique(db, kb_id, [category_name, *alias_list])

    parent: ProductCategory | None = None
    parent_path: str | None = None
    depth = 0
    if parent_id is not None:
        parent = db.get(ProductCategory, parent_id)
        if parent is None or parent.kb_id != kb_id:
            raise ValidationError("Parent category not found")
        if parent.status != CategoryStatus.active:
            raise ValidationError("Parent category must be active")
        parent_path = parent.path
        depth = parent.depth + 1
        if depth > MAX_DEPTH:
            raise ValidationError(f"Depth exceeds maximum of {MAX_DEPTH}")

    if _sibling_code_exists(db, kb_id, parent_id, category_code):
        raise AliasConflictError(
            f"Category code already exists: {category_code}",
            field="category_code",
            value=category_code,
        )

    category_id = uuid4()
    path = build_path(parent_path, str(category_id))
    assert_no_cycle(parent_path, str(category_id))

    category = ProductCategory(
        category_id=category_id,
        kb_id=kb_id,
        parent_id=parent_id,
        category_name=category_name,
        category_code=category_code,
        description=description,
        path=path,
        depth=depth,
        status=CategoryStatus.active,
    )
    db.add(category)
    db.flush()
    _add_aliases(db, category, alias_list)
    log_classification_audit(
        db,
        kb_id=kb_id,
        entity_type=AuditEntityType.product_category,
        entity_id=category.category_id,
        action=AuditAction.create,
        payload_summary={"category_name": category_name, "category_code": category_code},
    )
    db.commit()
    db.refresh(category)
    return category


def list_categories(
    db: Session,
    kb_id: UUID,
    *,
    status: CategoryStatus | None = CategoryStatus.active,
    include_inactive: bool = False,
) -> list[ProductCategory]:
    stmt = select(ProductCategory).where(ProductCategory.kb_id == kb_id)
    if not include_inactive and status is not None:
        stmt = stmt.where(ProductCategory.status == status)
    return list(db.scalars(stmt.order_by(ProductCategory.path)).all())


def build_tree_nodes(categories: list[ProductCategory]) -> list[dict]:
    by_id: dict[UUID, dict] = {}
    roots: list[dict] = []

    for cat in categories:
        node = {
            "category_id": str(cat.category_id),
            "parent_id": str(cat.parent_id) if cat.parent_id else None,
            "category_name": cat.category_name,
            "category_code": cat.category_code,
            "aliases": [a.alias for a in cat.aliases],
            "description": cat.description or "",
            "status": cat.status.value,
            "depth": cat.depth,
            "children": [],
        }
        by_id[cat.category_id] = node

    for cat in categories:
        node = by_id[cat.category_id]
        if cat.parent_id and cat.parent_id in by_id:
            by_id[cat.parent_id]["children"].append(node)
        else:
            roots.append(node)

    return roots


def get_category(db: Session, kb_id: UUID, category_id: UUID) -> ProductCategory | None:
    cat = db.get(ProductCategory, category_id)
    if cat is None or cat.kb_id != kb_id:
        return None
    return cat


def get_category_detail(db: Session, kb_id: UUID, category_id: UUID) -> dict | None:
    cat = get_category(db, kb_id, category_id)
    if cat is None:
        return None

    child_ids = list(
        db.scalars(
            select(ProductCategory.category_id).where(
                ProductCategory.parent_id == category_id,
                ProductCategory.kb_id == kb_id,
            )
        ).all()
    )

    breadcrumb: list[dict] = []
    if cat.path:
        path_ids = [p for p in cat.path.strip("/").split("/") if p]
        for pid in path_ids:
            ancestor = db.get(ProductCategory, UUID(pid))
            if ancestor:
                breadcrumb.append(
                    {
                        "category_id": str(ancestor.category_id),
                        "category_name": ancestor.category_name,
                    }
                )

    return {
        "category_id": str(cat.category_id),
        "parent_id": str(cat.parent_id) if cat.parent_id else None,
        "category_name": cat.category_name,
        "category_code": cat.category_code,
        "description": cat.description or "",
        "status": cat.status.value,
        "depth": cat.depth,
        "aliases": [a.alias for a in cat.aliases],
        "child_ids": [str(cid) for cid in child_ids],
        "breadcrumb": breadcrumb,
        "created_at": cat.created_at.isoformat(),
        "updated_at": cat.updated_at.isoformat(),
    }


def update_category(
    db: Session,
    category: ProductCategory,
    *,
    category_name: str | None = None,
    description: str | None = None,
    status: CategoryStatus | None = None,
) -> ProductCategory:
    if category_name is not None:
        alias_registry.check_unique(
            db,
            category.kb_id,
            [category_name],
            exclude_category_id=category.category_id,
        )
        category.category_name = category_name
    if description is not None:
        category.description = description
    if status is not None:
        if category.status == CategoryStatus.merged:
            raise InvalidStateError("Cannot change status of merged category")
        category.status = status
    log_classification_audit(
        db,
        kb_id=category.kb_id,
        entity_type=AuditEntityType.product_category,
        entity_id=category.category_id,
        action=AuditAction.update,
        payload_summary={
            "category_name": category_name,
            "description": description,
            "status": status.value if status else None,
        },
    )
    db.commit()
    db.refresh(category)
    return category


def replace_aliases(
    db: Session,
    category: ProductCategory,
    aliases: list[str],
) -> ProductCategory:
    alias_list = alias_registry.filter_extra_names(category.category_name, aliases)
    alias_registry.check_unique(
        db,
        category.kb_id,
        [category.category_name, *alias_list],
        exclude_category_id=category.category_id,
    )
    for existing in list(category.aliases):
        db.delete(existing)
    db.flush()
    _add_aliases(db, category, alias_list)
    log_classification_audit(
        db,
        kb_id=category.kb_id,
        entity_type=AuditEntityType.product_category,
        entity_id=category.category_id,
        action=AuditAction.update,
        payload_summary={"aliases": alias_list},
    )
    db.commit()
    db.refresh(category)
    return category


def search_categories(
    db: Session,
    kb_id: UUID,
    *,
    q: str,
    limit: int = 20,
    status: CategoryStatus = CategoryStatus.active,
) -> list[dict]:
    norm_q = normalize(q)
    pattern = f"%{q}%"
    stmt = (
        select(ProductCategory)
        .where(
            ProductCategory.kb_id == kb_id,
            ProductCategory.status == status,
            or_(
                ProductCategory.category_name.ilike(pattern),
                ProductCategory.category_id.in_(
                    select(ProductCategoryAlias.category_id).where(
                        ProductCategoryAlias.kb_id == kb_id,
                        ProductCategoryAlias.alias_normalized.contains(norm_q),
                    )
                ),
            ),
        )
        .limit(limit)
    )
    results: list[dict] = []
    for cat in db.scalars(stmt).all():
        matched_alias = None
        for alias in cat.aliases:
            if norm_q in alias.alias_normalized:
                matched_alias = alias.alias
                break
        path_labels = []
        for pid in cat.path.strip("/").split("/"):
            if not pid:
                continue
            ancestor = db.get(ProductCategory, UUID(pid))
            if ancestor:
                path_labels.append(ancestor.category_name)
        results.append(
            {
                "category_id": str(cat.category_id),
                "category_name": cat.category_name,
                "matched_alias": matched_alias,
                "path_labels": path_labels,
            }
        )
    return results


def deactivate_category(db: Session, category: ProductCategory) -> ProductCategory:
    active_children = db.scalar(
        select(ProductCategory.category_id).where(
            ProductCategory.parent_id == category.category_id,
            ProductCategory.status == CategoryStatus.active,
        )
    )
    if active_children is not None:
        raise InvalidStateError(
            "Category has active children", code="HAS_ACTIVE_CHILDREN"
        )
    category.status = CategoryStatus.inactive
    log_classification_audit(
        db,
        kb_id=category.kb_id,
        entity_type=AuditEntityType.product_category,
        entity_id=category.category_id,
        action=AuditAction.deactivate,
    )
    db.commit()
    db.refresh(category)
    return category


def archive_category(db: Session, category: ProductCategory) -> ProductCategory:
    category.status = CategoryStatus.archived
    log_classification_audit(
        db,
        kb_id=category.kb_id,
        entity_type=AuditEntityType.product_category,
        entity_id=category.category_id,
        action=AuditAction.archive,
    )
    db.commit()
    db.refresh(category)
    return category
