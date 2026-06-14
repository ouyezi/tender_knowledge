from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/candidates/batch",
    tags=["candidate-batch"],
)


@router.post("/confirm")
def batch_confirm(
    kb_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
):
    _ = db
    return JSONResponse(
        status_code=501,
        content=error("NOT_IMPLEMENTED", "batch confirm not implemented yet", trace_id=get_trace_id()),
    )


@router.post("/reject")
def batch_reject(
    kb_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
):
    _ = db
    return JSONResponse(
        status_code=501,
        content=error("NOT_IMPLEMENTED", "batch reject not implemented yet", trace_id=get_trace_id()),
    )
