import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class AuditEntityType(str, enum.Enum):
    product_category = "product_category"
    chapter_taxonomy = "chapter_taxonomy"


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    alias_add = "alias_add"
    alias_remove = "alias_remove"
    bind = "bind"
    unbind = "unbind"
    deactivate = "deactivate"
    archive = "archive"
    merge = "merge"


class ClassificationAuditLog(Base):
    __tablename__ = "classification_audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[AuditEntityType] = mapped_column(Enum(AuditEntityType), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    payload_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
