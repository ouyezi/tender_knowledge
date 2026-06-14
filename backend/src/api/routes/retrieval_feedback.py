from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_operator_id, get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.retrieval_feedback import RetrievalFeedbackType
from src.services.retrieval.feedback import RetrievalFeedbackService

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/retrieval/feedback",
    tags=["retrieval-feedback"],
)


class CreateFeedbackRequest(BaseModel):
    trace_id: UUID
    feedback_type: RetrievalFeedbackType
    object_type: str | None = None
    object_id: UUID | None = None
    rank_position: int | None = None
    expected_object_ids: list[str] = Field(default_factory=list)
    comment: str | None = None
    filter_adjustment: dict = Field(default_factory=dict)


class PromoteFeedbackRequest(BaseModel):
    eval_set_id: UUID
    expected_object_ids: list[str] = Field(default_factory=list)
    negative_object_ids: list[str] = Field(default_factory=list)


@router.post("")
def create_retrieval_feedback(
    kb_id: UUID,
    body: CreateFeedbackRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = RetrievalFeedbackService(db)
    try:
        row = service.create_feedback(
            kb_id=kb_id,
            trace_id=body.trace_id,
            feedback_type=body.feedback_type,
            object_type=body.object_type,
            object_id=body.object_id,
            rank_position=body.rank_position,
            expected_object_ids=body.expected_object_ids,
            comment=body.comment,
            filter_adjustment=body.filter_adjustment,
            operator_id=get_operator_id(),
        )
    except ValueError as exc:
        if str(exc) == "TRACE_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content=error("TRACE_NOT_FOUND", "retrieval trace not found", trace_id=get_trace_id()),
            )
        if str(exc) == "FALSE_NEGATIVE_MISSING_EXPECTATION":
            return JSONResponse(
                status_code=422,
                content=error(
                    "FALSE_NEGATIVE_MISSING_EXPECTATION",
                    "false_negative feedback requires expected_object_ids or comment",
                    trace_id=get_trace_id(),
                ),
            )
        raise
    db.commit()
    return success(
        {
            "feedback_id": str(row.feedback_id),
            "trace_id": str(row.trace_id),
            "feedback_type": row.feedback_type.value,
            "created_at": row.created_at.isoformat(),
        },
        trace_id=get_trace_id(),
    )


@router.get("")
def list_retrieval_feedback(
    kb_id: UUID,
    trace_id: UUID | None = None,
    feedback_type: RetrievalFeedbackType | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    data = RetrievalFeedbackService(db).list_feedback(
        kb_id=kb_id,
        trace_id=trace_id,
        feedback_type=feedback_type,
        from_dt=_parse_dt(from_),
        to_dt=_parse_dt(to),
        page=max(1, page),
        page_size=max(1, min(200, page_size)),
    )
    return success(data, trace_id=get_trace_id())


@router.post("/{feedback_id}/promote-to-eval-case")
def promote_feedback_to_eval_case(
    kb_id: UUID,
    feedback_id: UUID,
    body: PromoteFeedbackRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = RetrievalFeedbackService(db)
    try:
        row = service.promote_to_eval_case(
            kb_id=kb_id,
            feedback_id=feedback_id,
            eval_set_id=body.eval_set_id,
            expected_object_ids=body.expected_object_ids,
            negative_object_ids=body.negative_object_ids,
        )
    except ValueError as exc:
        code = str(exc)
        if code in {"FEEDBACK_NOT_FOUND", "EVAL_SET_NOT_FOUND", "TRACE_NOT_FOUND"}:
            return JSONResponse(
                status_code=404,
                content=error(code, code.lower().replace("_", " "), trace_id=get_trace_id()),
            )
        raise
    db.commit()
    return success({"eval_case_id": str(row.eval_case_id), "status": row.status.value}, trace_id=get_trace_id())


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    return datetime.fromisoformat(text)
