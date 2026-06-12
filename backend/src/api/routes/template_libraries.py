from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.template_library import TemplateLibrary

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/template-libraries",
    tags=["template-libraries"],
)


@router.get("")
def list_template_libraries(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(TemplateLibrary).filter(TemplateLibrary.kb_id == kb_id)
    total = q.count()
    rows = (
        q.order_by(TemplateLibrary.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "template_library_id": str(row.template_library_id),
            "library_name": row.library_name,
            "library_type": row.library_type.value,
            "status": row.status.value,
            "version": row.version,
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]
    return success(
        {"items": items, "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )
