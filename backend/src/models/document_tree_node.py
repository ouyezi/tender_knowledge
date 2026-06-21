import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class DocumentTreeNodeType(str, enum.Enum):
    heading = "heading"
    paragraph = "paragraph"
    table = "table"
    image = "image"
    other = "other"


class DocumentTreeNode(Base):
    __tablename__ = "document_tree_nodes"
    __table_args__ = (
        Index(
            "ix_document_tree_nodes_doc_parent_order", "document_id", "parent_id", "sort_order"
        ),
        Index("ix_document_tree_nodes_doc_tree_version", "document_id", "tree_version"),
    )

    node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_tree_nodes.node_id"), nullable=True
    )
    node_type: Mapped[DocumentTreeNodeType] = mapped_column(Enum(DocumentTreeNodeType), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    content_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    is_outline_node: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    candidate_template_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    candidate_pattern_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tree_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
