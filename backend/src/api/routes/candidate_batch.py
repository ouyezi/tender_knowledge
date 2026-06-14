from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.candidate_confirm_audit_log import CandidateConfirmAuditAction
from src.models.knowledge_base import KnowledgeBase
from src.services.candidate_adapter import CandidateNotFoundError
from src.services.candidate_audit_service import write_audit
from src.services.candidate_publish_service import PublishConflictError, publish
from src.services.candidate_publish_validator import PublishValidationError

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/candidates/batch",
    tags=["candidate-batch"],
)


MAX_BATCH_ITEMS = 100


class BatchConfirmItem(BaseModel):
    candidate_id: str
    confirm_as: str
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    product_category_ids: list[UUID] | None = None
    chapter_taxonomy_id: UUID | None = None
    knowledge_type: str | None = None
    wiki_type: str | None = None
    asset_type: str | None = None
    searchable: bool | None = True
    usage_hint: str | None = None
    review_comment: str | None = None
    template_id: UUID | None = None
    parent_chapter_id: UUID | None = None
    category_code: str | None = None
    parent_category_id: UUID | None = None
    storage_path: str | None = None


class BatchConfirmRequest(BaseModel):
    items: list[BatchConfirmItem]
    batch_comment: str | None = None


class BatchRejectRequest(BaseModel):
    candidate_ids: list[str]
    review_comment: str | None = None


def _batch_too_large_response(trace_id: UUID) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content=error(
            "BATCH_TOO_LARGE",
            f"Batch size exceeds limit {MAX_BATCH_ITEMS}",
            trace_id=trace_id,
        ),
    )


def _format_error(exc: Exception) -> dict:
    if isinstance(exc, CandidateNotFoundError):
        return {"code": "CANDIDATE_NOT_FOUND", "message": "Candidate not found"}
    if isinstance(exc, PublishValidationError):
        return {"code": exc.code, "message": str(exc)}
    if isinstance(exc, PublishConflictError):
        return {"code": "PUBLISH_CONFLICT", "message": str(exc)}
    return {"code": "PUBLISH_VALIDATION_FAILED", "message": str(exc)}


def _format_finished_at(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@router.post("/confirm")
def batch_confirm(
    kb_id: UUID,
    body: BatchConfirmRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    trace_id = get_trace_id() or UUID(int=0)
    total = len(body.items)
    if total > MAX_BATCH_ITEMS:
        return _batch_too_large_response(trace_id)

    batch_id = uuid4()
    results: list[dict] = []
    succeeded = 0
    failed = 0
    finished_at = datetime.now(timezone.utc)

    for item in body.items:
        try:
            publish_result = publish(
                db,
                kb_id=kb_id,
                candidate_id=item.candidate_id,
                payload=item.model_dump(exclude_unset=True),
                operator_id=operator_id,
                trace_id=trace_id,
            )
            results.append(
                {
                    "candidate_id": item.candidate_id,
                    "status": publish_result["status"],
                    "confirmed_object_type": publish_result["confirmed_object_type"],
                    "confirmed_object_id": publish_result["confirmed_object_id"],
                    "error": None,
                }
            )
            succeeded += 1
        except Exception as exc:
            failed += 1
            results.append(
                {
                    "candidate_id": item.candidate_id,
                    "status": "pending",
                    "confirmed_object_type": None,
                    "confirmed_object_id": None,
                    "error": _format_error(exc),
                }
            )

    write_audit(
        db,
        kb_id=kb_id,
        candidate_id=f"batch:{batch_id}",
        action=CandidateConfirmAuditAction.batch_confirm,
        operator_id=operator_id,
        trace_id=trace_id,
        batch_id=batch_id,
        detail={
            "batch_comment": body.batch_comment,
            "items": results,
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
        },
    )
    db.commit()
    finished_at = datetime.now(timezone.utc)

    return success(
        {
            "batch_id": str(batch_id),
            "trace_id": str(trace_id),
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "finished_at": _format_finished_at(finished_at),
        },
        trace_id=trace_id,
    )


@router.post("/reject")
def batch_reject(
    kb_id: UUID,
    body: BatchRejectRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    trace_id = get_trace_id() or UUID(int=0)
    total = len(body.candidate_ids)
    if total > MAX_BATCH_ITEMS:
        return _batch_too_large_response(trace_id)

    batch_id = uuid4()
    results: list[dict] = []
    succeeded = 0
    failed = 0

    for candidate_id in body.candidate_ids:
        try:
            publish(
                db,
                kb_id=kb_id,
                candidate_id=candidate_id,
                payload={"confirm_as": "ignore", "review_comment": body.review_comment},
                operator_id=operator_id,
                trace_id=trace_id,
            )
            results.append(
                {
                    "candidate_id": candidate_id,
                    "status": "rejected",
                    "error": None,
                }
            )
            succeeded += 1
        except Exception as exc:
            failed += 1
            results.append(
                {
                    "candidate_id": candidate_id,
                    "status": "pending",
                    "error": _format_error(exc),
                }
            )

    write_audit(
        db,
        kb_id=kb_id,
        candidate_id=f"batch:{batch_id}",
        action=CandidateConfirmAuditAction.batch_reject,
        operator_id=operator_id,
        trace_id=trace_id,
        batch_id=batch_id,
        detail={
            "batch_comment": body.review_comment,
            "items": results,
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
        },
    )
    db.commit()

    return success(
        {
            "batch_id": str(batch_id),
            "trace_id": str(trace_id),
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "finished_at": _format_finished_at(datetime.now(timezone.utc)),
        },
        trace_id=trace_id,
    )
