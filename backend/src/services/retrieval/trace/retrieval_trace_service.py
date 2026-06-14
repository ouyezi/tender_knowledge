from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.retrieval_trace import RetrievalIntent, RetrievalTrace, RetrievalTraceStatus


class RetrievalTraceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def write_trace(
        self,
        *,
        kb_id: UUID,
        intent: RetrievalIntent,
        request_snapshot: dict,
        stages: dict,
        response_summary: dict,
        strategy_version_id: UUID | None = None,
        operator_id: str | None = None,
        status: RetrievalTraceStatus = RetrievalTraceStatus.success,
        error_message: str | None = None,
        started_at_ms: float | None = None,
    ) -> RetrievalTrace:
        elapsed_ms = None
        if started_at_ms is not None:
            elapsed_ms = max(1, int((time.perf_counter() - started_at_ms) * 1000))
        trace = RetrievalTrace(
            kb_id=kb_id,
            intent=intent,
            strategy_version_id=strategy_version_id,
            request_snapshot=request_snapshot,
            response_summary=response_summary,
            stages=stages,
            status=status,
            error_message=error_message,
            latency_ms=elapsed_ms,
            operator_id=operator_id,
        )
        self.db.add(trace)
        self.db.flush()
        return trace
