from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, Integer, SmallInteger, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class UsageMode(str, enum.Enum):
    DIRECT = "DIRECT"
    REFERENCE = "REFERENCE"
    EXTRACT = "EXTRACT"


class TechniqueStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class WritingTechnique(Base):
    __tablename__ = "writing_techniques"
    __table_args__ = (
        Index("ix_writing_techniques_kb_id", "kb_id"),
        Index("ix_writing_techniques_kb_status", "kb_id", "status"),
    )

    technique_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    applicable_scene: Mapped[str | None] = mapped_column(Text, nullable=True)
    writing_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_sections: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    usage_mode: Mapped[UsageMode] = mapped_column(
        Enum(UsageMode, native_enum=False, length=20),
        nullable=False,
        default=UsageMode.REFERENCE,
    )
    recommended_outline: Mapped[str | None] = mapped_column(Text, nullable=True)
    writing_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    must_include: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklist: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    source_chunk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_invalid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[TechniqueStatus] = mapped_column(
        Enum(TechniqueStatus, native_enum=False, length=20),
        nullable=False,
        default=TechniqueStatus.draft,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
