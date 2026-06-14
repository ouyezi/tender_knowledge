import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ActualBidAuditLog(Base):
    __tablename__ = "actual_bid_audit_logs"
    __table_args__ = (
        Index(
            "ix_actual_bid_audit_logs_kb_obj_created",
            "kb_id",
            "object_type",
            "object_id",
            "created_at",
        ),
    )

    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    operator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
