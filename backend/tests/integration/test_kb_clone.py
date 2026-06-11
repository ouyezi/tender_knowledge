from sqlalchemy import select

from src.models.kb_clone_log import KBCloneLog
from src.services import kb_service
from src.services.kb_clone_service import clone_kb


def test_clone_empty_kb_writes_log(db_session):
    source = kb_service.create_kb(db_session, "source-kb")
    target = kb_service.create_kb(db_session, "target-kb")
    clone_kb(
        db_session,
        source.kb_id,
        target.kb_id,
        operator_id="admin",
        trace_id="trace-1",
    )
    log = db_session.scalar(
        select(KBCloneLog).where(KBCloneLog.target_kb_id == target.kb_id)
    )
    assert log is not None
    assert log.source_kb_id == source.kb_id
    assert source.kb_id != target.kb_id
