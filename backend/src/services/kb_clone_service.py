from uuid import UUID

from sqlalchemy.orm import Session

from src.models.kb_clone_log import KBCloneLog

MAX_NODES = 2000


def clone_kb(
    db: Session,
    source_kb_id: UUID,
    target_kb_id: UUID,
    *,
    operator_id: str,
    trace_id: str,
) -> None:
    """Deep-clone classification trees from source to target KB.

    Epic 0 P0: writes audit log; full tree copy extended in Task 7+.
    """
    log = KBCloneLog(
        target_kb_id=target_kb_id,
        source_kb_id=source_kb_id,
        operator_id=operator_id,
        trace_id=trace_id,
    )
    db.add(log)
    db.commit()
