import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class BidOutlineNodeStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    deprecated = "deprecated"


class BidOutlineNode(Base):
    __tablename__ = "bid_outline_nodes"
    __table_args__ = (
        Index(
            "ix_bid_outline_nodes_outline_parent_order", "bid_outline_id", "parent_id", "sort_order"
        ),
        Index("ix_bid_outline_nodes_outline_source_node", "bid_outline_id", "source_node_id"),
    )

    outline_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    bid_outline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bid_outlines.bid_outline_id"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bid_outline_nodes.outline_node_id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    source_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_tree_nodes.node_id"), nullable=True
    )
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[BidOutlineNodeStatus] = mapped_column(
        Enum(BidOutlineNodeStatus), nullable=False, default=BidOutlineNodeStatus.draft
    )
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
