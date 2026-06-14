from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.candidate_confirm_audit_log import (
    CandidateConfirmAuditAction,
    CandidateConfirmAuditLog,
)
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.candidate_knowledge_stub import CandidateKnowledgeStub
from src.models.knowledge_base import KnowledgeBase

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/candidate-audit-logs",
    tags=["candidate-audit-logs"],
)


def _format_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _serialize_row(row: CandidateConfirmAuditLog) -> dict:
    return {
        "audit_id": str(row.audit_id),
        "candidate_id": row.candidate_id,
        "batch_id": str(row.batch_id) if row.batch_id else None,
        "action": row.action.value,
        "operator_id": row.operator_id,
        "trace_id": str(row.trace_id),
        "detail": row.detail,
        "created_at": _format_dt(row.created_at),
    }


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _candidate_ids_for_import(db: Session, *, kb_id: UUID, import_id: UUID) -> list[str]:
    doc_ids = [
        f"doc_{row.candidate_id}"
        for row in db.query(CandidateKnowledge.candidate_id)
        .filter(CandidateKnowledge.kb_id == kb_id)
        .filter(CandidateKnowledge.import_id == import_id)
        .all()
    ]
    tpl_ids = [
        f"tpl_{row.stub_id}"
        for row in db.query(CandidateKnowledgeStub.stub_id)
        .filter(CandidateKnowledgeStub.kb_id == kb_id)
        .filter(CandidateKnowledgeStub.import_id == import_id)
        .all()
    ]
    return doc_ids + tpl_ids


@router.get("")
def list_candidate_audit_logs(
    kb_id: UUID,
    candidate_id: str | None = None,
    import_id: UUID | None = None,
    batch_id: UUID | None = None,
    action: str | None = None,
    operator_id: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    q = db.query(CandidateConfirmAuditLog).filter(CandidateConfirmAuditLog.kb_id == kb_id)

    if candidate_id:
        q = q.filter(CandidateConfirmAuditLog.candidate_id == candidate_id)
    if import_id:
        allowed_ids = _candidate_ids_for_import(db, kb_id=kb_id, import_id=import_id)
        if not allowed_ids:
            return success(
                {"items": [], "total": 0, "page": page, "page_size": page_size},
                trace_id=get_trace_id(),
            )
        q = q.filter(CandidateConfirmAuditLog.candidate_id.in_(allowed_ids))
    if batch_id:
        q = q.filter(CandidateConfirmAuditLog.batch_id == batch_id)
    if action:
        q = q.filter(CandidateConfirmAuditLog.action == CandidateConfirmAuditAction(action))
    if operator_id:
        q = q.filter(CandidateConfirmAuditLog.operator_id == operator_id)

    from_dt = _parse_iso_datetime(from_)
    if from_dt:
        q = q.filter(CandidateConfirmAuditLog.created_at >= from_dt)
    to_dt = _parse_iso_datetime(to)
    if to_dt:
        q = q.filter(CandidateConfirmAuditLog.created_at <= to_dt)

    total = q.count()
    offset = max(page - 1, 0) * page_size
    rows = (
        q.order_by(CandidateConfirmAuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [_serialize_row(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


@router.get("/{audit_id}")
def get_candidate_audit_log(
    kb_id: UUID,
    audit_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(CandidateConfirmAuditLog)
        .filter(CandidateConfirmAuditLog.kb_id == kb_id)
        .filter(CandidateConfirmAuditLog.audit_id == audit_id)
        .first()
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error(
                "AUDIT_LOG_NOT_FOUND",
                "Audit log not found",
                trace_id=get_trace_id(),
            ),
        )
    return success(_serialize_row(row), trace_id=get_trace_id())
