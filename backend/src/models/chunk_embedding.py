from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint("object_type", "object_id", name="uq_chunk_embeddings_object"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_embedding: Mapped[Any] = mapped_column(
        JSON().with_variant(Vector(1024), "postgresql"), nullable=True
    )
    summary_embedding: Mapped[Any] = mapped_column(
        JSON().with_variant(Vector(1024), "postgresql"), nullable=True
    )
    title_embedding: Mapped[Any] = mapped_column(
        JSON().with_variant(Vector(1024), "postgresql"), nullable=True
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
