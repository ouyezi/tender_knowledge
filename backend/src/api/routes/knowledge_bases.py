from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id
from src.db.session import get_db
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.models.knowledge_base import KBStatus, KnowledgeBase
from src.services import kb_service

router = APIRouter(prefix="/api/v1/kbs", tags=["knowledge-bases"])


class CreateKBRequest(BaseModel):
    name: str


class PatchKBRequest(BaseModel):
    name: str


def _kb_dict(kb: KnowledgeBase) -> dict:
    return {
        "kb_id": str(kb.kb_id),
        "name": kb.name,
        "status": kb.status.value,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
    }


@router.post("")
def create_kb(
    body: CreateKBRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_operator_id),
):
    kb = kb_service.create_kb(db, body.name)
    return success(_kb_dict(kb), trace_id=get_trace_id())


@router.get("")
def list_kbs(status: str = "active", db: Session = Depends(get_db)):
    st = KBStatus(status) if status else None
    items = kb_service.list_kbs(db, st)
    return success(
        {"items": [_kb_dict(k) for k in items]},
        trace_id=get_trace_id(),
    )


@router.get("/{kb_id}")
def get_kb_detail(kb: KnowledgeBase = Depends(get_kb_or_404)):
    return success(_kb_dict(kb), trace_id=get_trace_id())


@router.patch("/{kb_id}")
def patch_kb(
    body: PatchKBRequest,
    kb: KnowledgeBase = Depends(get_kb_or_404),
    db: Session = Depends(get_db),
):
    kb = kb_service.update_kb_name(db, kb, body.name)
    return success(_kb_dict(kb), trace_id=get_trace_id())


@router.post("/{kb_id}/deactivate")
def deactivate_kb(
    kb: KnowledgeBase = Depends(get_kb_or_404),
    db: Session = Depends(get_db),
):
    kb = kb_service.deactivate_kb(db, kb)
    return success(_kb_dict(kb), trace_id=get_trace_id())
