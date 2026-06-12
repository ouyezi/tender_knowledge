from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.template import Template

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/templates",
    tags=["templates"],
)


@router.get("")
def list_templates(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    uncategorized: bool = False,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(Template).filter(Template.kb_id == kb_id)
    if uncategorized:
        q = q.filter(Template.template_library_id.is_(None))
    total = q.count()
    rows = (
        q.order_by(Template.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "template_id": str(row.template_id),
            "template_name": row.template_name,
            "template_library_id": str(row.template_library_id)
            if row.template_library_id
            else None,
            "status": row.status.value,
            "confirmed": row.confirmed,
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]
    return success(
        {"items": items, "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )
