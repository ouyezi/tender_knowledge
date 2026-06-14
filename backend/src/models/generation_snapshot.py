import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class GenerationSnapshot(Base):
    __tablename__ = "generation_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("generation_tasks.task_id"), nullable=False, unique=True
    )
    requirement_context_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tender_requirement_contexts.requirement_context_id"),
        nullable=False,
    )
    requirement_context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    suggestion_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    target_outline_node: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    used_ku_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    used_wiki_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    used_template_chapter_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    used_manual_asset_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    variable_inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    retrieval_trace_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    result_version: Mapped[str] = mapped_column(String(64), nullable=False)
    conflict_hints: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    missing_material_hints: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    input_priority_layers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
