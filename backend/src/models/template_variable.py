import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateVariableValueType(str, enum.Enum):
    string = "string"
    number = "number"
    date = "date"
    enum = "enum"
    text = "text"


class TemplateVariableStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class TemplateVariable(Base):
    __tablename__ = "template_variables"
    __table_args__ = (
        Index("uq_template_variables_tpl_key", "template_id", "variable_key", unique=True),
    )

    variable_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.template_id"), nullable=False
    )
    template_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_chapters.template_chapter_id"), nullable=True
    )
    variable_key: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    value_type: Mapped[TemplateVariableValueType] = mapped_column(
        Enum(TemplateVariableValueType), nullable=False, default=TemplateVariableValueType.string
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    placeholder_pattern: Mapped[str] = mapped_column(String(64), nullable=False, default="{{key}}")
    status: Mapped[TemplateVariableStatus] = mapped_column(
        Enum(TemplateVariableStatus), nullable=False, default=TemplateVariableStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
