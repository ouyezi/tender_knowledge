import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class TenderRequirementStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class TenderRequirementContext(Base):
    __tablename__ = "tender_requirement_contexts"
    __table_args__ = (
        Index(
            "ix_tender_requirement_contexts_kb_status_created",
            "kb_id",
            "status",
            "created_at",
        ),
    )

    requirement_context_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    outline_structure: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    outline_nodes: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    score_points: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    rejection_clauses: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    format_requirements: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    qualification_requirements: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    response_clauses: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TenderRequirementStatus] = mapped_column(
        Enum(TenderRequirementStatus), nullable=False, default=TenderRequirementStatus.active
    )
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
