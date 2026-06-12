from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.template_parse_task import TemplateParseTask

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/template-parse",
    tags=["template-parse"],
)


@router.get("/tasks")
def list_parse_tasks(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(TemplateParseTask).filter(TemplateParseTask.kb_id == kb_id)
    total = q.count()
    rows = (
        q.order_by(TemplateParseTask.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "parse_task_id": str(row.parse_task_id),
            "import_id": str(row.import_id),
            "template_id": str(row.template_id) if row.template_id else None,
            "status": row.status.value,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
    return success(
        {"items": items, "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )
