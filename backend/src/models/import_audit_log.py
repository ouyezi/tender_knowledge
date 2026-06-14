import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ImportAuditAction(str, enum.Enum):
    upload = "upload"
    suggest_ready = "suggest_ready"
    confirm = "confirm"
    ignore = "ignore"
    retry = "retry"
    duplicate_skip = "duplicate_skip"
    duplicate_new_version = "duplicate_new_version"
    route = "route"
    delete = "delete"
    purge_all = "purge_all"


class ImportAuditLog(Base):
    __tablename__ = "import_audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("file_imports.import_id", ondelete="SET NULL"),
        nullable=True,
    )
    operator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[ImportAuditAction] = mapped_column(Enum(ImportAuditAction), nullable=False)
    payload_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
