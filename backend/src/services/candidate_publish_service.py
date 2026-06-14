from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.candidate_confirm_audit_log import CandidateConfirmAuditAction
from src.models.candidate_knowledge import CandidateKnowledgeStatus
from src.models.candidate_knowledge_stub import CandidateKnowledgeStubStatus
from src.services.candidate_adapter import (
    CandidateNotFoundError,
    get_document_row,
    get_stub_row,
    load_candidate,
)
from src.services.candidate_audit_service import write_audit
from src.services.candidate_publish_validator import PublishValidationError, validate_publish
from src.services.publishers import (
    chapter_pattern_publisher,
    ignore_handler,
    ku_publisher,
    manual_asset_publisher,
    product_category_publisher,
    template_chapter_publisher,
    wiki_publisher,
)


class PublishConflictError(Exception):
    pass


PUBLISHERS = {
    "ku": ku_publisher.publish,
    "wiki": wiki_publisher.publish,
    "template_chapter": template_chapter_publisher.publish,
    "manual_asset": manual_asset_publisher.publish,
    "chapter_pattern": chapter_pattern_publisher.publish,
    "product_category": product_category_publisher.publish,
    "ignore": ignore_handler.publish,
}


def _load_row(db: Session, *, kb_id: UUID, candidate_id: str, channel: str):
    if channel == "document":
        return get_document_row(db, kb_id=kb_id, candidate_id=candidate_id)
    return get_stub_row(db, kb_id=kb_id, candidate_id=candidate_id)


def _is_published_status(status: str) -> bool:
    return status in {"published", "rejected"}


def _normalize_row_status(channel: str, status: str):
    if channel == "document":
        return CandidateKnowledgeStatus(status)
    if status == "published":
        return CandidateKnowledgeStubStatus.published
    return CandidateKnowledgeStubStatus.rejected


def publish(
    db: Session,
    *,
    kb_id: UUID,
    candidate_id: str,
    payload: dict,
    operator_id: str,
    trace_id: UUID,
) -> dict:
    view = load_candidate(db, kb_id=kb_id, candidate_id=candidate_id)
    confirm_as = payload.get("confirm_as")
    if confirm_as not in PUBLISHERS:
        raise PublishValidationError("confirm_as is invalid")

    if _is_published_status(view.status):
        if view.confirmed_object_type == confirm_as:
            return {
                "candidate_id": view.candidate_id,
                "confirmed_object_type": view.confirmed_object_type,
                "confirmed_object_id": str(view.confirmed_object_id)
                if view.confirmed_object_id
                else None,
                "status": view.status,
                "trace_id": str(trace_id),
                "idempotent": True,
            }
        raise PublishConflictError("candidate already published with different confirm_as")

    try:
        validate_publish(
            db=db,
            kb_id=kb_id,
            confirm_as=confirm_as,
            payload=payload,
            view=view,
        )
        result = PUBLISHERS[confirm_as](
            db,
            kb_id=kb_id,
            view=view,
            payload=payload,
            operator_id=operator_id,
        )
        row = _load_row(db, kb_id=kb_id, candidate_id=candidate_id, channel=view.channel)
        row.status = _normalize_row_status(view.channel, result["status"])
        row.confirmed_object_type = result["confirmed_object_type"]
        row.confirmed_object_id = result["confirmed_object_id"]
        row.searchable = payload.get("searchable", True)
        row.usage_hint = payload.get("usage_hint")
        row.review_comment = payload.get("review_comment")
        row.updated_by = operator_id
        row.updated_at = datetime.now(timezone.utc)
        row.last_publish_error = None

        write_audit(
            db,
            kb_id=kb_id,
            candidate_id=view.candidate_id,
            action=(
                CandidateConfirmAuditAction.ignore
                if confirm_as == "ignore"
                else CandidateConfirmAuditAction.publish
            ),
            operator_id=operator_id,
            trace_id=trace_id,
            detail={
                "confirm_as": confirm_as,
                "confirmed_object_type": result["confirmed_object_type"],
                "confirmed_object_id": str(result["confirmed_object_id"])
                if result["confirmed_object_id"]
                else None,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        failure_row = _load_row(db, kb_id=kb_id, candidate_id=candidate_id, channel=view.channel)
        failure_row.last_publish_error = str(exc)
        failure_row.publish_attempt_count = (failure_row.publish_attempt_count or 0) + 1
        failure_row.updated_by = operator_id
        failure_row.updated_at = datetime.now(timezone.utc)
        write_audit(
            db,
            kb_id=kb_id,
            candidate_id=view.candidate_id,
            action=CandidateConfirmAuditAction.publish_failed,
            operator_id=operator_id,
            trace_id=trace_id,
            detail={"confirm_as": confirm_as, "error": str(exc), "error_code": getattr(exc, "code", "PUBLISH_VALIDATION_FAILED")},
        )
        db.commit()
        raise

    return {
        "candidate_id": view.candidate_id,
        "confirmed_object_type": result["confirmed_object_type"],
        "confirmed_object_id": str(result["confirmed_object_id"])
        if result["confirmed_object_id"]
        else None,
        "status": result["status"],
        "trace_id": str(trace_id),
        "idempotent": False,
    }
