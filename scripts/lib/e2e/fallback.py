from __future__ import annotations

from uuid import UUID

from src.db.session import SessionLocal
from src.models.downstream_task_entry import DownstreamTaskEntry, DownstreamTaskStatus, DownstreamTaskType
from src.services.actual_bid_parse_runner import _run_entry as run_actual_bid_entry
from src.services.template_parse_runner import _run_entry as run_template_entry


def run_actual_bid_fallback(import_id: str) -> bool:
    with SessionLocal() as db:
        entry = (
            db.query(DownstreamTaskEntry)
            .filter(
                DownstreamTaskEntry.import_id == UUID(import_id),
                DownstreamTaskEntry.task_type == DownstreamTaskType.document_parse,
                DownstreamTaskEntry.status == DownstreamTaskStatus.pending,
            )
            .order_by(DownstreamTaskEntry.created_at.desc())
            .first()
        )
        if entry is None:
            return False
        entry.status = DownstreamTaskStatus.claimed
        entry.claimed_by = "e2e-pipeline"
        db.flush()
        run_actual_bid_entry(db, entry)
        db.commit()
        return True


def run_template_fallback(import_id: str) -> bool:
    with SessionLocal() as db:
        entry = (
            db.query(DownstreamTaskEntry)
            .filter(
                DownstreamTaskEntry.import_id == UUID(import_id),
                DownstreamTaskEntry.task_type == DownstreamTaskType.template_file_parse,
                DownstreamTaskEntry.status == DownstreamTaskStatus.pending,
            )
            .order_by(DownstreamTaskEntry.created_at.desc())
            .first()
        )
        if entry is None:
            from src.services.template_parse_runner import run_template_parse_pending

            run_template_parse_pending(db)
            db.commit()
            return True
        entry.status = DownstreamTaskStatus.claimed
        entry.claimed_by = "e2e-pipeline"
        db.flush()
        run_template_entry(db, entry)
        db.commit()
        return True
