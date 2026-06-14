from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.wiki import Wiki

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/wikis",
    tags=["wikis"],
)


@router.get("")
def list_wikis(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(Wiki).filter(Wiki.kb_id == kb_id)
    total = q.count()
    rows = q.order_by(Wiki.updated_at.desc()).offset(offset).limit(page_size).all()
    return success(
        {
            "items": [
                {
                    "wiki_id": str(row.wiki_id),
                    "title": row.title,
                    "summary": row.summary,
                    "content": row.content,
                    "wiki_type": row.wiki_type,
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


@router.get("/{wiki_id}")
def get_wiki(
    kb_id: UUID,
    wiki_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(Wiki)
        .filter(Wiki.kb_id == kb_id)
        .filter(Wiki.wiki_id == wiki_id)
        .one_or_none()
    )
    if row is None:
        return success(None, trace_id=get_trace_id())
    return success(
        {
            "wiki_id": str(row.wiki_id),
            "title": row.title,
            "summary": row.summary,
            "content": row.content,
            "wiki_type": row.wiki_type,
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
