from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    JSON,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index(
            "uq_knowledge_chunks_latest_node",
            "kb_id",
            "doc_id",
            "primary_node_id",
            unique=True,
            postgresql_where=text("is_latest = true"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    knowledge_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    doc_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    catalog_path: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    primary_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    block_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    application_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    business_line_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    regions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    certificate_number: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    certificate_date: Mapped[str | None] = mapped_column(String(512), nullable=True)
    expire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    template_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    security_level: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    has_children: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    children_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
