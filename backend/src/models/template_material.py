import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateMaterialType(str, enum.Enum):
    docx_section = "docx_section"
    ppt_material = "ppt_material"
    image = "image"
    table = "table"
    fixed_paragraph = "fixed_paragraph"
    cover_guide = "cover_guide"
    writing_guide = "writing_guide"
    excel_table = "excel_table"
    other = "other"


class TemplateMaterialStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    deprecated = "deprecated"


class TemplateMaterial(Base):
    __tablename__ = "template_materials"

    material_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.template_id"), nullable=False
    )
    template_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_chapters.template_chapter_id"), nullable=True
    )
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=True
    )
    material_type: Mapped[TemplateMaterialType] = mapped_column(
        Enum(TemplateMaterialType), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    extract_as_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[TemplateMaterialStatus] = mapped_column(
        Enum(TemplateMaterialStatus), nullable=False, default=TemplateMaterialStatus.draft
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
