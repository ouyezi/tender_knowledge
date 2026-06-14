import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class CandidateConfirmAuditAction(str, enum.Enum):
    edit = "edit"
    publish = "publish"
    publish_failed = "publish_failed"
    ignore = "ignore"
    merge = "merge"
    split = "split"
    batch_confirm = "batch_confirm"
    batch_reject = "batch_reject"


class CandidateConfirmAuditLog(Base):
    __tablename__ = "candidate_confirm_audit_logs"
    __table_args__ = (
        Index(
            "ix_candidate_confirm_audit_kb_candidate_created",
            "kb_id",
            "candidate_id",
            "created_at",
        ),
        Index("ix_candidate_confirm_audit_kb_batch", "kb_id", "batch_id"),
        Index("ix_candidate_confirm_audit_kb_action_created", "kb_id", "action", "created_at"),
    )

    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    action: Mapped[CandidateConfirmAuditAction] = mapped_column(
        Enum(CandidateConfirmAuditAction), nullable=False
    )
    operator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
