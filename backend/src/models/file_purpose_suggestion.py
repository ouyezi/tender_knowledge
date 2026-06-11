import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base
from src.models.file_import import FilePurpose


class SuggestionSource(str, enum.Enum):
    rule = "rule"
    llm = "llm"
    hybrid = "hybrid"


class FilePurposeSuggestion(Base):
    __tablename__ = "file_purpose_suggestions"

    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False, unique=True
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    suggested_purpose: Mapped[FilePurpose | None] = mapped_column(Enum(FilePurpose), nullable=True)
    purpose_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    suggested_chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    suggestion_source: Mapped[SuggestionSource] = mapped_column(
        Enum(SuggestionSource), nullable=False, default=SuggestionSource.rule
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
