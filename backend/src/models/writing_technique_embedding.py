from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class WritingTechniqueEmbedding(Base):
    __tablename__ = "writing_technique_embeddings"

    technique_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("writing_techniques.technique_id", ondelete="CASCADE"),
        primary_key=True,
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[Any] = mapped_column(Vector(1024), nullable=True)
    embedding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
