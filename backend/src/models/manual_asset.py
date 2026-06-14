import enum
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ManualAssetStatus(str, enum.Enum):
    published = "published"
    deprecated = "deprecated"


class ManualAsset(Base):
    __tablename__ = "manual_assets"
    __table_args__ = (
        Index("ix_manual_assets_kb_type_status", "kb_id", "asset_type", "status"),
        Index("ix_manual_assets_kb_candidate", "kb_id", "candidate_id", unique=True),
    )

    manual_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=True
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[ManualAssetStatus] = mapped_column(
        Enum(ManualAssetStatus), nullable=False, default=ManualAssetStatus.published
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str] = mapped_column(String(128), nullable=False)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
