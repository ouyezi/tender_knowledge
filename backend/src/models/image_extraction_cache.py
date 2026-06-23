from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ImageExtractionCache(Base):
    __tablename__ = "image_extraction_cache"

    md5_hash: Mapped[str] = mapped_column(String(32), primary_key=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    vision_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
