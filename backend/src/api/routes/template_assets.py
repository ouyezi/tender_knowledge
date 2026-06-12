from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/templates/{template_id}",
    tags=["template-assets"],
)


@router.get("/materials")
def list_materials(
    kb_id: UUID,
    template_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _ = db, template_id
    return success({"items": [], "total": 0}, trace_id=get_trace_id())


@router.get("/variables")
def list_variables(
    kb_id: UUID,
    template_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _ = db, template_id
    return success({"items": [], "total": 0}, trace_id=get_trace_id())


@router.get("/rules")
def list_rules(
    kb_id: UUID,
    template_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _ = db, template_id
    return success({"items": [], "total": 0}, trace_id=get_trace_id())
