import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ChapterPatternStatus(str, enum.Enum):
    candidate = "candidate"
    confirmed = "confirmed"
    deprecated = "deprecated"


class ChapterPattern(Base):
    __tablename__ = "chapter_patterns"

    pattern_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    pattern_name: Mapped[str] = mapped_column(String(256), nullable=False)
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    common_child_chapters: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    source_outline_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    source_template_chapter_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ChapterPatternStatus] = mapped_column(
        Enum(ChapterPatternStatus), nullable=False, default=ChapterPatternStatus.candidate
    )
    mining_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_pattern_mining_tasks.mining_task_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
