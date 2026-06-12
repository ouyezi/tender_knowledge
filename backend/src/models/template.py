import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateType(str, enum.Enum):
    technical_bid = "technical_bid"
    commercial_bid = "commercial_bid"
    qualification = "qualification"
    chapter_set = "chapter_set"
    custom = "custom"


class TemplateStatus(str, enum.Enum):
    draft = "draft"
    reviewing = "reviewing"
    published = "published"
    deprecated = "deprecated"


class Template(Base):
    __tablename__ = "templates"
    __table_args__ = (
        Index("ix_templates_kb_library_status", "kb_id", "template_library_id", "status"),
        Index("ix_templates_kb_source_import", "kb_id", "source_import_id"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    template_library_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_libraries.template_library_id"), nullable=True
    )
    source_import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    template_name: Mapped[str] = mapped_column(String(512), nullable=False)
    template_type: Mapped[TemplateType] = mapped_column(Enum(TemplateType), nullable=False)
    product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    applicable_project_types: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    applicable_customer_types: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    status: Mapped[TemplateStatus] = mapped_column(
        Enum(TemplateStatus), nullable=False, default=TemplateStatus.draft
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    structure_locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    structure_locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
