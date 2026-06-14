from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.candidate_confirm_audit_log import (
    CandidateConfirmAuditAction,
    CandidateConfirmAuditLog,
)


def write_audit(
    db: Session,
    *,
    kb_id: UUID,
    candidate_id: str,
    action: CandidateConfirmAuditAction,
    operator_id: str,
    trace_id: UUID,
    detail: dict[str, Any] | None = None,
    batch_id: UUID | None = None,
) -> CandidateConfirmAuditLog:
    row = CandidateConfirmAuditLog(
        kb_id=kb_id,
        candidate_id=candidate_id,
        batch_id=batch_id,
        action=action,
        operator_id=operator_id,
        trace_id=trace_id,
        detail=detail or {},
    )
    db.add(row)
    return row
