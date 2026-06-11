from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.knowledge_base import KnowledgeBase, KBStatus


def create_kb(db: Session, name: str) -> KnowledgeBase:
    kb = KnowledgeBase(name=name, status=KBStatus.active)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def list_kbs(db: Session, status: KBStatus | None = KBStatus.active) -> list[KnowledgeBase]:
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at)
    if status is not None:
        stmt = stmt.where(KnowledgeBase.status == status)
    return list(db.scalars(stmt))


def get_kb(db: Session, kb_id: UUID) -> KnowledgeBase | None:
    return db.get(KnowledgeBase, kb_id)


def update_kb_name(db: Session, kb: KnowledgeBase, name: str) -> KnowledgeBase:
    kb.name = name
    db.commit()
    db.refresh(kb)
    return kb


def deactivate_kb(db: Session, kb: KnowledgeBase) -> KnowledgeBase:
    kb.status = KBStatus.inactive
    db.commit()
    db.refresh(kb)
    return kb
