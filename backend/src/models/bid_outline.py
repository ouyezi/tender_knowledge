import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class BidOutlineType(str, enum.Enum):
    actual_bid = "actual_bid"
    manual = "manual"


class BidOutlineStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    published = "published"
    deprecated = "deprecated"


class BidOutlineExtractStrategy(str, enum.Enum):
    toc = "toc"
    heading_heuristic = "heading_heuristic"
    flat_fallback = "flat_fallback"


class BidOutline(Base):
    __tablename__ = "bid_outlines"
    __table_args__ = (
        Index("ix_bid_outlines_kb_source_doc", "kb_id", "source_doc_id"),
        Index("ix_bid_outlines_kb_status_updated", "kb_id", "status", "updated_at"),
    )

    bid_outline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    source_doc_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    outline_name: Mapped[str] = mapped_column(String(512), nullable=False)
    outline_type: Mapped[BidOutlineType] = mapped_column(
        Enum(BidOutlineType), nullable=False, default=BidOutlineType.actual_bid
    )
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    project_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[BidOutlineStatus] = mapped_column(
        Enum(BidOutlineStatus), nullable=False, default=BidOutlineStatus.draft
    )
    extract_strategy: Mapped[BidOutlineExtractStrategy] = mapped_column(
        Enum(BidOutlineExtractStrategy), nullable=False, default=BidOutlineExtractStrategy.toc
    )
    structure_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    structure_locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
