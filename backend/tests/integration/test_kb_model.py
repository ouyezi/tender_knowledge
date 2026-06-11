from sqlalchemy import select

from src.models.knowledge_base import KnowledgeBase, KBStatus


def test_create_knowledge_base(db_session):
    kb = KnowledgeBase(name="标书知识库-demo", status=KBStatus.active)
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)

    found = db_session.scalar(
        select(KnowledgeBase).where(KnowledgeBase.name == "标书知识库-demo")
    )
    assert found is not None
    assert found.status == KBStatus.active
