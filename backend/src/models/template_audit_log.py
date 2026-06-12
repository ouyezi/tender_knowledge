import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateAuditAction(str, enum.Enum):
    parse_start = "parse_start"
    parse_complete = "parse_complete"
    parse_fail = "parse_fail"
    confirm = "confirm"
    chapter_update = "chapter_update"
    material_update = "material_update"
    variable_update = "variable_update"
    rule_update = "rule_update"
    publish = "publish"
    deprecate = "deprecate"
    diff_apply = "diff_apply"
    diff_reject = "diff_reject"


class TemplateAuditLog(Base):
    __tablename__ = "template_audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.template_id"), nullable=True
    )
    template_library_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_libraries.template_library_id"), nullable=True
    )
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=True
    )
    operator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[TemplateAuditAction] = mapped_column(Enum(TemplateAuditAction), nullable=False)
    payload_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
