from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.knowledge_unit import KnowledgeUnit

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/knowledge-units",
    tags=["knowledge-units"],
)


@router.get("")
def list_knowledge_units(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(KnowledgeUnit).filter(KnowledgeUnit.kb_id == kb_id)
    total = q.count()
    rows = (
        q.order_by(KnowledgeUnit.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [
                {
                    "ku_id": str(row.ku_id),
                    "title": row.title,
                    "summary": row.summary,
                    "content": row.content,
                    "knowledge_type": row.knowledge_type,
                    "product_category_ids": row.product_category_ids,
                    "chapter_taxonomy_id": str(row.chapter_taxonomy_id)
                    if row.chapter_taxonomy_id
                    else None,
                    "import_id": str(row.import_id),
                    "candidate_id": str(row.candidate_id),
                    "source_doc_id": str(row.source_doc_id) if row.source_doc_id else None,
                    "source_node_id": str(row.source_node_id) if row.source_node_id else None,
                    "searchable": row.searchable,
                    "usage_hint": row.usage_hint,
                    "status": row.status.value,
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


@router.get("/{ku_id}")
def get_knowledge_unit(
    kb_id: UUID,
    ku_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(KnowledgeUnit)
        .filter(KnowledgeUnit.kb_id == kb_id)
        .filter(KnowledgeUnit.ku_id == ku_id)
        .one_or_none()
    )
    if row is None:
        return success(None, trace_id=get_trace_id())
    return success(
        {
            "ku_id": str(row.ku_id),
            "title": row.title,
            "summary": row.summary,
            "content": row.content,
            "knowledge_type": row.knowledge_type,
            "product_category_ids": row.product_category_ids,
            "chapter_taxonomy_id": str(row.chapter_taxonomy_id)
            if row.chapter_taxonomy_id
            else None,
            "import_id": str(row.import_id),
            "candidate_id": str(row.candidate_id),
            "source_doc_id": str(row.source_doc_id) if row.source_doc_id else None,
            "source_node_id": str(row.source_node_id) if row.source_node_id else None,
            "searchable": row.searchable,
            "usage_hint": row.usage_hint,
            "status": row.status.value,
        },
        trace_id=get_trace_id(),
    )
