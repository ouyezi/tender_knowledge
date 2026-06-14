from __future__ import annotations

import re
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models.product_category import CategoryStatus, ProductCategory


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return slug or f"category-{uuid4().hex[:8]}"


def publish(
    db: Session,
    *,
    kb_id: UUID,
    view,
    payload: dict,
    operator_id: str,
) -> dict:
    _ = (view, operator_id)
    title = payload.get("title")
    parent_id = payload.get("parent_category_id")
    parent = None
    if parent_id:
        parent = (
            db.query(ProductCategory)
            .filter(ProductCategory.kb_id == kb_id)
            .filter(ProductCategory.category_id == UUID(str(parent_id)))
            .one_or_none()
        )
    category_id = uuid4()
    row = ProductCategory(
        category_id=category_id,
        kb_id=kb_id,
        parent_id=parent.category_id if parent else None,
        category_name=title,
        category_code=payload.get("category_code") or _slugify(title),
        description=payload.get("summary"),
        status=CategoryStatus.active,
        path="",
        depth=(parent.depth + 1) if parent else 0,
    )
    row.path = f"{parent.path}{category_id}/" if parent else f"/{category_id}/"
    db.add(row)
    db.flush()
    return {
        "confirmed_object_type": "product_category",
        "confirmed_object_id": row.category_id,
        "status": "published",
    }
