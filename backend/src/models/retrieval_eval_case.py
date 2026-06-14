import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base
from src.models.retrieval_trace import RetrievalIntent


class RetrievalEvalCaseCreatedFrom(str, enum.Enum):
    manual = "manual"
    user_feedback = "user_feedback"
    production_log = "production_log"


class RetrievalEvalCaseStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


class RetrievalEvalCase(Base):
    __tablename__ = "retrieval_eval_cases"

    eval_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    eval_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("retrieval_eval_sets.eval_set_id"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[RetrievalIntent] = mapped_column(Enum(RetrievalIntent), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    expected_object_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    negative_object_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    chapter_taxonomy_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    created_from: Mapped[RetrievalEvalCaseCreatedFrom] = mapped_column(
        Enum(RetrievalEvalCaseCreatedFrom),
        nullable=False,
        default=RetrievalEvalCaseCreatedFrom.manual,
    )
    source_feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("retrieval_feedbacks.feedback_id"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[RetrievalEvalCaseStatus] = mapped_column(
        Enum(RetrievalEvalCaseStatus), nullable=False, default=RetrievalEvalCaseStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
