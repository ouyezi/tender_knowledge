from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus
from src.services.retrieval.indexing.index_builder import IndexBuilder


def publish(
    db: Session,
    *,
    kb_id: UUID,
    view,
    payload: dict,
    operator_id: str,
) -> dict:
    row = KnowledgeUnit(
        kb_id=kb_id,
        title=payload.get("title") or view.title,
        summary=payload.get("summary", view.summary),
        content=payload.get("content") or view.content,
        knowledge_type=payload.get("knowledge_type") or view.suggested_knowledge_type,
        product_category_ids=[
            str(item)
            for item in (
                payload.get("product_category_ids")
                or view.suggested_product_category_ids
                or []
            )
        ],
        chapter_taxonomy_id=payload.get("chapter_taxonomy_id")
        or view.suggested_chapter_taxonomy_id,
        import_id=UUID(view.source_trace["import_id"]),
        candidate_id=view.raw_id,
        source_doc_id=UUID(view.source_trace["source_doc_id"])
        if view.source_trace.get("source_doc_id")
        else None,
        source_node_id=UUID(view.source_trace["source_node_id"])
        if view.source_trace.get("source_node_id")
        else None,
        searchable=payload.get("searchable", True),
        usage_hint=payload.get("usage_hint"),
        status=KnowledgeUnitStatus.published,
        published_at=datetime.now(timezone.utc),
        published_by=operator_id,
    )
    db.add(row)
    db.flush()
    IndexBuilder(db).upsert_from_ku(row)
    return {
        "confirmed_object_type": "ku",
        "confirmed_object_id": row.ku_id,
        "status": "published",
    }
