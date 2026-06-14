import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class RetrievalIntent(str, enum.Enum):
    knowledge_lookup = "knowledge_lookup"
    material_recommend = "material_recommend"
    module_suggestion = "module_suggestion"
    trace_lookup = "trace_lookup"
    directory_match = "directory_match"


class RetrievalTraceStatus(str, enum.Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


class RetrievalTrace(Base):
    __tablename__ = "retrieval_traces"
    __table_args__ = (
        Index("ix_retrieval_traces_kb_intent_created", "kb_id", "intent", "created_at"),
    )

    trace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    intent: Mapped[RetrievalIntent] = mapped_column(Enum(RetrievalIntent), nullable=False)
    strategy_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retrieval_strategy_versions.strategy_version_id"),
        nullable=True,
    )
    request_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    response_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    stages: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[RetrievalTraceStatus] = mapped_column(
        Enum(RetrievalTraceStatus), nullable=False, default=RetrievalTraceStatus.success
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
