from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session


def publish(
    db: Session,
    *,
    kb_id: UUID,
    view,
    payload: dict,
    operator_id: str,
) -> dict:
    _ = (db, kb_id, view, payload, operator_id)
    return {
        "confirmed_object_type": "ignore",
        "confirmed_object_id": None,
        "status": "rejected",
    }
