import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class DownstreamTaskType(str, enum.Enum):
    document_parse = "document_parse"
    bid_outline_extract = "bid_outline_extract"
    candidate_knowledge_generate = "candidate_knowledge_generate"
    template_file_parse = "template_file_parse"
    manual_asset_candidate = "manual_asset_candidate"
    template_material_ingest = "template_material_ingest"
    wiki_candidate = "wiki_candidate"
    none = "none"
    attachment_only = "attachment_only"


class DownstreamTaskStatus(str, enum.Enum):
    pending = "pending"
    claimed = "claimed"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class DownstreamTaskEntry(Base):
    __tablename__ = "downstream_task_entries"
    __table_args__ = (
        Index("ix_downstream_tasks_kb_type_status", "kb_id", "task_type", "status"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    task_type: Mapped[DownstreamTaskType] = mapped_column(Enum(DownstreamTaskType), nullable=False)
    status: Mapped[DownstreamTaskStatus] = mapped_column(
        Enum(DownstreamTaskStatus), nullable=False, default=DownstreamTaskStatus.pending
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
