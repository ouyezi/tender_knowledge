from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Index, SmallInteger, String, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class KnowledgeTaxonomy(Base):
    __tablename__ = "knowledge_taxonomy"
    __table_args__ = (
        Index("uq_knowledge_taxonomy_dimension_code", "dimension", "code", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(128), nullable=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
