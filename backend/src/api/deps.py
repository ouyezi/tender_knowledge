from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from src.api.middleware.audit import set_operator_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase, KBStatus
from src.services import kb_service


def get_operator_id(
    x_operator_id: str = Header(default="system", alias="X-Operator-Id"),
) -> str:
    set_operator_id(x_operator_id)
    return x_operator_id


def get_kb_or_404(kb_id: UUID, db: Session = Depends(get_db)) -> KnowledgeBase:
    kb = kb_service.get_kb(db, kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="KB not found")
    return kb


def kb_write_guard(kb: KnowledgeBase = Depends(get_kb_or_404)) -> KnowledgeBase:
    if kb.status == KBStatus.inactive:
        raise HTTPException(
            status_code=403,
            detail={"code": "KB_READ_ONLY", "message": "KB is read-only"},
        )
    return kb
