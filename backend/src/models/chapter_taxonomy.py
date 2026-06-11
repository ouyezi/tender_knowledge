import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base
from src.models.product_category import CategoryStatus


class BindingSource(str, enum.Enum):
    manual = "manual"
    suggested = "suggested"
    imported = "imported"


class ChapterTaxonomy(Base):
    __tablename__ = "chapter_taxonomies"

    taxonomy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    standard_name: Mapped[str] = mapped_column(String(128), nullable=False)
    taxonomy_code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CategoryStatus] = mapped_column(
        Enum(CategoryStatus), nullable=False, default=CategoryStatus.active
    )
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    synonyms: Mapped[list["ChapterTaxonomySynonym"]] = relationship(
        back_populates="taxonomy", cascade="all, delete-orphan"
    )
    bindings: Mapped[list["ChapterTaxonomyBinding"]] = relationship(
        back_populates="taxonomy", cascade="all, delete-orphan"
    )


class ChapterTaxonomySynonym(Base):
    __tablename__ = "chapter_taxonomy_synonyms"

    synonym_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    taxonomy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    synonym: Mapped[str] = mapped_column(String(128), nullable=False)
    synonym_normalized: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    taxonomy: Mapped[ChapterTaxonomy] = relationship(back_populates="synonyms")


class ChapterTaxonomyBinding(Base):
    __tablename__ = "chapter_taxonomy_bindings"

    binding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    taxonomy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=False
    )
    category_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source: Mapped[BindingSource] = mapped_column(
        Enum(BindingSource), nullable=False, default=BindingSource.manual
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")

    taxonomy: Mapped[ChapterTaxonomy] = relationship(back_populates="bindings")
