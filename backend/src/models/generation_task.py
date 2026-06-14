import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class GenerationTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class GenerationTask(Base):
    __tablename__ = "generation_tasks"
    __table_args__ = (
        Index("ix_generation_tasks_kb_status_created", "kb_id", "status", "created_at"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    requirement_context_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_requirement_contexts.requirement_context_id"),
        nullable=False,
    )
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("module_assembly_suggestions.suggestion_id"),
        nullable=True,
    )
    target_outline_node: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[GenerationTaskStatus] = mapped_column(
        Enum(GenerationTaskStatus), nullable=False, default=GenerationTaskStatus.pending
    )
    request_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "chapter_drafts.draft_id",
            use_alter=True,
            name="fk_generation_tasks_draft_id",
        ),
        nullable=True,
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
