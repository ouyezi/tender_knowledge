import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class RetrievalStrategyVersion(Base):
    __tablename__ = "retrieval_strategy_versions"
    __table_args__ = (
        Index(
            "ix_retrieval_strategy_versions_kb_active",
            "kb_id",
            "is_active",
        ),
    )

    strategy_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    embedding_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rerank_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
