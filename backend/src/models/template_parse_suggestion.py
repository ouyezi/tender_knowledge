import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TemplateSuggestionSource(str, enum.Enum):
    rule = "rule"
    llm = "llm"
    hybrid = "hybrid"


class TemplateParseSuggestion(Base):
    __tablename__ = "template_parse_suggestions"

    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parse_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_parse_tasks.parse_task_id"), nullable=False, unique=True
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    suggested_library_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_libraries.template_library_id"), nullable=True
    )
    suggested_library_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    suggested_product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    suggested_chapter_tree: Mapped[dict[str, Any] | list[Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    suggested_materials: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    suggested_candidates: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    suggestion_source: Mapped[TemplateSuggestionSource] = mapped_column(
        Enum(TemplateSuggestionSource), nullable=False, default=TemplateSuggestionSource.rule
    )
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
