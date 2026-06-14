from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.retrieval_eval_case import (
    RetrievalEvalCase,
    RetrievalEvalCaseCreatedFrom,
    RetrievalEvalCaseStatus,
)
from src.models.retrieval_eval_set import RetrievalEvalSet
from src.models.retrieval_feedback import RetrievalFeedback, RetrievalFeedbackType
from src.models.retrieval_trace import RetrievalIntent, RetrievalTrace


class RetrievalFeedbackService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_feedback(
        self,
        *,
        kb_id: UUID,
        trace_id: UUID,
        feedback_type: RetrievalFeedbackType,
        object_type: str | None,
        object_id: UUID | None,
        rank_position: int | None,
        expected_object_ids: list[str] | None,
        comment: str | None,
        filter_adjustment: dict | None,
        operator_id: str | None,
    ) -> RetrievalFeedback:
        trace = (
            self.db.query(RetrievalTrace)
            .filter(RetrievalTrace.kb_id == kb_id, RetrievalTrace.trace_id == trace_id)
            .one_or_none()
        )
        if trace is None:
            raise ValueError("TRACE_NOT_FOUND")
        if feedback_type == RetrievalFeedbackType.false_negative:
            has_expected = bool(expected_object_ids)
            has_comment = bool((comment or "").strip())
            if not has_expected and not has_comment:
                raise ValueError("FALSE_NEGATIVE_MISSING_EXPECTATION")

        feedback = RetrievalFeedback(
            kb_id=kb_id,
            trace_id=trace_id,
            feedback_type=feedback_type,
            object_type=object_type,
            object_id=object_id,
            rank_position=rank_position,
            expected_object_ids=expected_object_ids or [],
            comment=(comment or "").strip() or None,
            filter_adjustment=filter_adjustment or None,
            operator_id=operator_id,
        )
        self.db.add(feedback)
        self.db.flush()
        return feedback

    def list_feedback(
        self,
        *,
        kb_id: UUID,
        trace_id: UUID | None,
        feedback_type: RetrievalFeedbackType | None,
        from_dt: datetime | None,
        to_dt: datetime | None,
        page: int,
        page_size: int,
    ) -> dict:
        query = self.db.query(RetrievalFeedback).filter(RetrievalFeedback.kb_id == kb_id)
        if trace_id is not None:
            query = query.filter(RetrievalFeedback.trace_id == trace_id)
        if feedback_type is not None:
            query = query.filter(RetrievalFeedback.feedback_type == feedback_type)
        if from_dt is not None:
            query = query.filter(RetrievalFeedback.created_at >= from_dt)
        if to_dt is not None:
            query = query.filter(RetrievalFeedback.created_at <= to_dt)

        total = query.count()
        rows = (
            query.order_by(RetrievalFeedback.created_at.desc())
            .offset(max(0, page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [
                {
                    "feedback_id": str(row.feedback_id),
                    "trace_id": str(row.trace_id),
                    "feedback_type": row.feedback_type.value,
                    "object_type": row.object_type,
                    "object_id": str(row.object_id) if row.object_id else None,
                    "rank_position": row.rank_position,
                    "expected_object_ids": row.expected_object_ids or [],
                    "comment": row.comment,
                    "filter_adjustment": row.filter_adjustment,
                    "operator_id": row.operator_id,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def promote_to_eval_case(
        self,
        *,
        kb_id: UUID,
        feedback_id: UUID,
        eval_set_id: UUID,
        expected_object_ids: list[str] | None,
        negative_object_ids: list[str] | None,
    ) -> RetrievalEvalCase:
        feedback = (
            self.db.query(RetrievalFeedback)
            .filter(RetrievalFeedback.kb_id == kb_id, RetrievalFeedback.feedback_id == feedback_id)
            .one_or_none()
        )
        if feedback is None:
            raise ValueError("FEEDBACK_NOT_FOUND")

        eval_set = (
            self.db.query(RetrievalEvalSet)
            .filter(RetrievalEvalSet.kb_id == kb_id, RetrievalEvalSet.eval_set_id == eval_set_id)
            .one_or_none()
        )
        if eval_set is None:
            raise ValueError("EVAL_SET_NOT_FOUND")

        trace = (
            self.db.query(RetrievalTrace)
            .filter(RetrievalTrace.kb_id == kb_id, RetrievalTrace.trace_id == feedback.trace_id)
            .one_or_none()
        )
        if trace is None:
            raise ValueError("TRACE_NOT_FOUND")

        request_snapshot = trace.request_snapshot or {}
        raw_intent = request_snapshot.get("intent") or trace.intent.value
        try:
            intent = RetrievalIntent(raw_intent)
        except ValueError:
            intent = trace.intent

        eval_case = RetrievalEvalCase(
            eval_set_id=eval_set_id,
            kb_id=kb_id,
            query=request_snapshot.get("query") or "",
            intent=intent,
            filters=request_snapshot.get("filters") or {},
            expected_object_ids=expected_object_ids or feedback.expected_object_ids or [],
            negative_object_ids=negative_object_ids or [],
            product_category_ids=request_snapshot.get("product_category_ids") or [],
            chapter_taxonomy_ids=request_snapshot.get("chapter_taxonomy_ids") or [],
            created_from=RetrievalEvalCaseCreatedFrom.user_feedback,
            source_feedback_id=feedback.feedback_id,
            status=RetrievalEvalCaseStatus.pending,
        )
        self.db.add(eval_case)
        self.db.flush()
        return eval_case
