import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class WikiStatus(str, enum.Enum):
    published = "published"
    deprecated = "deprecated"


class Wiki(Base):
    __tablename__ = "wikis"
    __table_args__ = (
        Index("ix_wikis_kb_status", "kb_id", "status"),
        Index("ix_wikis_kb_candidate", "kb_id", "candidate_id", unique=True),
    )

    wiki_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    wiki_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=True
    )
    source_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_tree_nodes.node_id"), nullable=True
    )
    searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    usage_hint: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[WikiStatus] = mapped_column(
        Enum(WikiStatus), nullable=False, default=WikiStatus.published
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
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
