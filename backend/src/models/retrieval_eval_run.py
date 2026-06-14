import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class RetrievalEvalRunStatus(str, enum.Enum):
    running = "running"
    success = "success"
    failed = "failed"


class RetrievalEvalRun(Base):
    __tablename__ = "retrieval_eval_runs"

    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    eval_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("retrieval_eval_sets.eval_set_id"), nullable=False
    )
    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retrieval_strategy_versions.strategy_version_id"),
        nullable=False,
    )
    baseline_strategy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retrieval_strategy_versions.strategy_version_id"),
        nullable=True,
    )
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    comparison_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[RetrievalEvalRunStatus] = mapped_column(
        Enum(RetrievalEvalRunStatus), nullable=False, default=RetrievalEvalRunStatus.running
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
