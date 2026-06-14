from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/candidate-audit-logs",
    tags=["candidate-audit-logs"],
)


@router.get("")
def list_candidate_audit_logs(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _ = db
    return success(
        {"items": [], "total": 0, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )
