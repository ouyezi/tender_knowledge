import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class RetrievalFeedbackType(str, enum.Enum):
    click = "click"
    adopt = "adopt"
    copy = "copy"
    add_to_draft = "add_to_draft"
    useful = "useful"
    not_useful = "not_useful"
    false_positive = "false_positive"
    false_negative = "false_negative"


class RetrievalFeedback(Base):
    __tablename__ = "retrieval_feedbacks"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("retrieval_traces.trace_id"), nullable=False
    )
    feedback_type: Mapped[RetrievalFeedbackType] = mapped_column(
        Enum(RetrievalFeedbackType), nullable=False
    )
    object_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    object_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    rank_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_object_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_adjustment: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
