import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class DocumentSourceType(str, enum.Enum):
    actual_bid = "actual_bid"
    template_file = "template_file"


class DocumentSourceUsage(str, enum.Enum):
    knowledge_extract = "knowledge_extract"
    reference_only = "reference_only"


class DocumentParseStatus(str, enum.Enum):
    pending = "pending"
    parsing = "parsing"
    ready = "ready"
    failed = "failed"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_kb_import", "kb_id", "import_id"),
        Index("ix_documents_kb_source_updated", "kb_id", "source_type", "updated_at"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    source_type: Mapped[DocumentSourceType] = mapped_column(Enum(DocumentSourceType), nullable=False)
    source_usage: Mapped[DocumentSourceUsage] = mapped_column(
        Enum(DocumentSourceUsage), nullable=False, default=DocumentSourceUsage.knowledge_extract
    )
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    bid_project_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bid_customer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    document_name: Mapped[str] = mapped_column(String(512), nullable=False)
    parse_status: Mapped[DocumentParseStatus] = mapped_column(
        Enum(DocumentParseStatus), nullable=False, default=DocumentParseStatus.pending
    )
    tree_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confirmed_metadata: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
