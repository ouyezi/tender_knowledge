import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateChapterStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    deprecated = "deprecated"


class TemplateChapter(Base):
    __tablename__ = "template_chapters"
    __table_args__ = (
        Index("ix_template_chapters_tpl_parent_sort", "template_id", "parent_id", "sort_order"),
        Index("ix_template_chapters_kb_taxonomy", "kb_id", "chapter_taxonomy_id"),
    )

    template_chapter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.template_id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_chapters.template_chapter_id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    expected_knowledge_types: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    bound_wiki_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    bound_ku_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    bound_material_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    variable_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    rule_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_fixed_section: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ignored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parse_source_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[TemplateChapterStatus] = mapped_column(
        Enum(TemplateChapterStatus), nullable=False, default=TemplateChapterStatus.draft
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
