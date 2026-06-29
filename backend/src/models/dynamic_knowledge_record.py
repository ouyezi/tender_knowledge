from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, Index, String, Text, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class DynamicKnowledgeRecord(Base):
    __tablename__ = "dynamic_knowledge_records"
    __table_args__ = (
        Index("ix_dynamic_knowledge_kb_type", "kb_id", "dynamic_type_code"),
        Index("ix_dynamic_knowledge_kb_status", "kb_id", "status"),
        Index("ix_dynamic_knowledge_expire", "kb_id", "expire_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    dynamic_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    structured_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    business_line_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="extracted")
    source_doc_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_chunk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
