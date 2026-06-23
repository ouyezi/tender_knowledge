from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    Float,
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
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    catalog_path: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    primary_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    need_parent_context: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quote_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="full")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    products: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    industries: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    customer_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    regions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    template_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variables: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclusion_rules: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    retrieval_weight: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("1.00")
    )
    security_level: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    winning_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    edit_distance_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
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
