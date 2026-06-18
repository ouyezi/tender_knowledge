from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ChunkAsset(Base):
    __tablename__ = "chunk_assets"
    __table_args__ = (
        Index("ix_chunk_assets_doc_range", "kb_id", "doc_id", "char_start", "char_end"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    doc_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    chunk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_schema: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    table_headers: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    table_rows: Mapped[list[list[str]] | None] = mapped_column(JSON, nullable=True)
    table_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allow_row_filter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    image_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_storage_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_with_text: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
