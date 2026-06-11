from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.api.middleware.audit import get_operator_id, get_trace_id
from src.models.audit_log import AuditAction, AuditEntityType, ClassificationAuditLog


def log_classification_audit(
    db: Session,
    *,
    kb_id: UUID,
    entity_type: AuditEntityType,
    entity_id: UUID,
    action: AuditAction,
    payload_summary: dict[str, Any] | None = None,
    trace_id: UUID | None = None,
    operator_id: str | None = None,
) -> ClassificationAuditLog:
    tid = trace_id or get_trace_id() or uuid4()
    op = operator_id or get_operator_id() or "system"
    entry = ClassificationAuditLog(
        trace_id=tid,
        kb_id=kb_id,
        operator_id=op,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload_summary=payload_summary,
    )
    db.add(entry)
    return entry
