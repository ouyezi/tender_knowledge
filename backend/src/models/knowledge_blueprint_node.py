from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ImportanceLevel(str, enum.Enum):
    required = "required"
    recommended = "recommended"
    optional = "optional"


class KnowledgeBlueprintNode(Base):
    __tablename__ = "knowledge_blueprint_nodes"
    __table_args__ = (
        Index("ix_knowledge_blueprint_nodes_blueprint_id", "blueprint_id"),
        Index("ix_knowledge_blueprint_nodes_parent_node_id", "parent_node_id"),
    )

    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_blueprints.blueprint_id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_blueprint_nodes.node_id", ondelete="CASCADE"),
        nullable=True,
    )
    node_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    node_title: Mapped[str] = mapped_column(String(200), nullable=False)
    node_level: Mapped[int] = mapped_column(Integer, nullable=False)
    node_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tender_response_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_level: Mapped[ImportanceLevel] = mapped_column(
        Enum(ImportanceLevel, native_enum=False, length=20), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
