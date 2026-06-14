import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class BidOutlineStructureDiffStatus(str, enum.Enum):
    pending = "pending"
    applied = "applied"
    rejected = "rejected"


class BidOutlineStructureDiff(Base):
    __tablename__ = "bid_outline_structure_diffs"

    diff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    bid_outline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("bid_outlines.bid_outline_id"), nullable=False
    )
    parse_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("actual_bid_parse_tasks.parse_task_id"), nullable=False
    )
    diff_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[BidOutlineStructureDiffStatus] = mapped_column(
        Enum(BidOutlineStructureDiffStatus),
        nullable=False,
        default=BidOutlineStructureDiffStatus.pending,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
