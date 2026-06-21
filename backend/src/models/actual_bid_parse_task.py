import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ActualBidParseTaskPhase(str, enum.Enum):
    document_parse = "document_parse"
    bid_outline_extract = "bid_outline_extract"
    candidate_generate = "candidate_generate"
    full_pipeline = "full_pipeline"


class ActualBidParseTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    ready = "ready"
    confirmed = "confirmed"
    failed = "failed"
    cancelled = "cancelled"


class ActualBidParseStrategy(str, enum.Enum):
    docx = "docx"


class ActualBidParseTask(Base):
    __tablename__ = "actual_bid_parse_tasks"
    __table_args__ = (
        Index("ix_actual_bid_parse_tasks_kb_import_status", "kb_id", "import_id", "status"),
        Index("ix_actual_bid_parse_tasks_kb_created", "kb_id", "created_at"),
    )

    parse_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=True
    )
    bid_outline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    task_phase: Mapped[ActualBidParseTaskPhase] = mapped_column(
        Enum(ActualBidParseTaskPhase),
        nullable=False,
        default=ActualBidParseTaskPhase.full_pipeline,
    )
    status: Mapped[ActualBidParseTaskStatus] = mapped_column(
        Enum(ActualBidParseTaskStatus), nullable=False, default=ActualBidParseTaskStatus.pending
    )
    parse_strategy: Mapped[ActualBidParseStrategy] = mapped_column(
        Enum(ActualBidParseStrategy), nullable=False, default=ActualBidParseStrategy.docx
    )
    downstream_entry_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_progress: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
