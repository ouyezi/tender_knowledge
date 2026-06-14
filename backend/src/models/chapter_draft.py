import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class DraftOutcomeStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    discarded = "discarded"


class ChapterDraft(Base):
    __tablename__ = "chapter_drafts"

    draft_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("generation_tasks.task_id"), nullable=False, unique=True
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("generation_snapshots.snapshot_id"), nullable=False
    )
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
    paragraphs: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    conflict_hints: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    missing_material_hints: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    outcome_status: Mapped[DraftOutcomeStatus] = mapped_column(
        Enum(DraftOutcomeStatus), nullable=False, default=DraftOutcomeStatus.pending
    )
    outcome_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version_tag: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
