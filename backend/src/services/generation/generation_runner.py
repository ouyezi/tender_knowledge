from __future__ import annotations

from uuid import UUID

from src.db.session import SessionLocal
from src.services.generation.generation_service import GenerationService


def run_generation_task_in_new_session(task_id: UUID) -> None:
    db = SessionLocal()
    try:
        GenerationService(db).run_task(task_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
