import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateParseTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    parse_ready = "parse_ready"
    confirmed = "confirmed"
    failed = "failed"
    cancelled = "cancelled"


class TemplateParseStrategy(str, enum.Enum):
    docx = "docx"
    ppt = "ppt"
    xlsx = "xlsx"
    pdf_fallback = "pdf_fallback"


class TemplateParseTask(Base):
    __tablename__ = "template_parse_tasks"
    __table_args__ = (
        Index("ix_template_parse_tasks_kb_import_status", "kb_id", "import_id", "status"),
        Index("ix_template_parse_tasks_kb_status_created", "kb_id", "status", "created_at"),
    )

    parse_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    downstream_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("downstream_task_entries.entry_id"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.template_id"), nullable=True
    )
    status: Mapped[TemplateParseTaskStatus] = mapped_column(
        Enum(TemplateParseTaskStatus), nullable=False, default=TemplateParseTaskStatus.pending
    )
    parse_strategy: Mapped[TemplateParseStrategy | None] = mapped_column(
        Enum(TemplateParseStrategy), nullable=True
    )
    log_lines: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_progress: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, default=uuid.uuid4)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
