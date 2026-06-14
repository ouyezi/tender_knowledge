from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.template_chapter import TemplateChapter, TemplateChapterStatus


def publish(
    db: Session,
    *,
    kb_id: UUID,
    view,
    payload: dict,
    operator_id: str,
) -> dict:
    template_id = payload.get("template_id") or view.source_trace.get("template_id")
    parent_id = payload.get("parent_chapter_id")
    current_max = (
        db.query(func.max(TemplateChapter.sort_order))
        .filter(TemplateChapter.template_id == UUID(str(template_id)))
        .scalar()
    )
    row = TemplateChapter(
        kb_id=kb_id,
        template_id=UUID(str(template_id)),
        parent_id=UUID(str(parent_id)) if parent_id else None,
        title=payload.get("title") or view.title,
        level=2 if parent_id else 1,
        sort_order=(current_max or 0) + 1,
        chapter_taxonomy_id=payload.get("chapter_taxonomy_id")
        or view.suggested_chapter_taxonomy_id,
        product_category_ids=[
            str(item)
            for item in (
                payload.get("product_category_ids")
                or view.suggested_product_category_ids
                or []
            )
        ],
        expected_knowledge_types=[payload.get("knowledge_type")]
        if payload.get("knowledge_type")
        else [],
        status=TemplateChapterStatus.published,
    )
    db.add(row)
    db.flush()
    return {
        "confirmed_object_type": "template_chapter",
        "confirmed_object_id": row.template_chapter_id,
        "status": "published",
    }
