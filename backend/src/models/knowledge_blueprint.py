from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class BlueprintStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class KnowledgeBlueprint(Base):
    __tablename__ = "knowledge_blueprints"
    __table_args__ = (
        UniqueConstraint("kb_id", "source_node_id", name="uq_blueprints_kb_source_node"),
        Index("ix_knowledge_blueprints_kb_id", "kb_id"),
    )

    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_doc_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_node_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_chapter_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    product_tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    industry_tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    scenario_tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    applicable_project_type: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    related_regulations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    overall_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    common_mistakes: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    usual_page_range: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BlueprintStatus] = mapped_column(
        Enum(BlueprintStatus, native_enum=False, length=20),
        nullable=False,
        default=BlueprintStatus.active,
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
