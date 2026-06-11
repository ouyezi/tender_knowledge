import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ImportTaskType(str, enum.Enum):
    file_import = "file_import"
    file_purpose_classify = "file_purpose_classify"


class ImportTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ImportTask(Base):
    __tablename__ = "import_tasks"
    __table_args__ = (
        Index("ix_import_tasks_kb_import_type", "kb_id", "import_id", "task_type"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    task_type: Mapped[ImportTaskType] = mapped_column(Enum(ImportTaskType), nullable=False)
    status: Mapped[ImportTaskStatus] = mapped_column(
        Enum(ImportTaskStatus), nullable=False, default=ImportTaskStatus.pending
    )
    log_lines: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, default=uuid.uuid4)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
