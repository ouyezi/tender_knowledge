import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateLibraryType(str, enum.Enum):
    technical = "technical"
    commercial = "commercial"
    qualification = "qualification"
    product_specific = "product_specific"
    custom = "custom"


class TemplateLibraryStatus(str, enum.Enum):
    draft = "draft"
    reviewing = "reviewing"
    published = "published"
    deprecated = "deprecated"


class TemplateLibrary(Base):
    __tablename__ = "template_libraries"
    __table_args__ = (
        Index("ix_template_libraries_kb_status_updated", "kb_id", "status", "updated_at"),
    )

    template_library_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    library_name: Mapped[str] = mapped_column(String(256), nullable=False)
    library_type: Mapped[TemplateLibraryType] = mapped_column(
        Enum(TemplateLibraryType), nullable=False
    )
    source_import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=True
    )
    product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_updated_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[TemplateLibraryStatus] = mapped_column(
        Enum(TemplateLibraryStatus), nullable=False, default=TemplateLibraryStatus.draft
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
