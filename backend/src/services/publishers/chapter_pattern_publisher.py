from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.chapter_pattern import ChapterPattern, ChapterPatternStatus


def publish(
    db: Session,
    *,
    kb_id: UUID,
    view,
    payload: dict,
    operator_id: str,
) -> dict:
    _ = operator_id
    title = payload.get("title") or view.title
    taxonomy_id = payload.get("chapter_taxonomy_id") or view.suggested_chapter_taxonomy_id
    row = (
        db.query(ChapterPattern)
        .filter(ChapterPattern.kb_id == kb_id)
        .filter(ChapterPattern.pattern_name == title)
        .filter(ChapterPattern.chapter_taxonomy_id == taxonomy_id)
        .one_or_none()
    )
    if row is None:
        row = ChapterPattern(
            kb_id=kb_id,
            pattern_name=title,
            chapter_taxonomy_id=taxonomy_id,
            product_category_ids=[
                str(item)
                for item in (
                    payload.get("product_category_ids")
                    or view.suggested_product_category_ids
                    or []
                )
            ],
            common_child_chapters=[],
            source_outline_ids=[str(view.source_trace["source_doc_id"])]
            if view.source_trace.get("source_doc_id")
            else [],
            source_template_chapter_ids=[str(view.source_trace["template_chapter_id"])]
            if view.source_trace.get("template_chapter_id")
            else [],
            frequency=1,
            status=ChapterPatternStatus.confirmed,
        )
        db.add(row)
    else:
        row.status = ChapterPatternStatus.confirmed
    db.flush()
    return {
        "confirmed_object_type": "chapter_pattern",
        "confirmed_object_id": row.pattern_id,
        "status": "published",
    }
