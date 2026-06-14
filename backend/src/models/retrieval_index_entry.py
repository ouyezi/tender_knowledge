import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Index, JSON, String, Text, Uuid, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class RetrievalObjectType(str, enum.Enum):
    ku = "ku"
    wiki = "wiki"
    template = "template"
    template_chapter = "template_chapter"
    bid_outline = "bid_outline"
    bid_outline_node = "bid_outline_node"
    chapter_pattern = "chapter_pattern"
    manual_asset = "manual_asset"


class RetrievalIndexStatus(str, enum.Enum):
    published = "published"
    deprecated = "deprecated"


class RetrievalIndexEntry(Base):
    __tablename__ = "retrieval_index_entries"
    __table_args__ = (
        UniqueConstraint(
            "kb_id",
            "object_type",
            "object_id",
            name="uq_retrieval_index_entries_kb_object",
        ),
        Index(
            "ix_retrieval_index_entries_kb_type_status",
            "kb_id",
            "object_type",
            "status",
        ),
        Index(
            "ix_retrieval_index_entries_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        Index(
            "ix_retrieval_index_entries_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    index_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    object_type: Mapped[RetrievalObjectType] = mapped_column(
        Enum(RetrievalObjectType), nullable=False
    )
    object_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    knowledge_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_purpose: Mapped[str | None] = mapped_column(String(64), nullable=True)
    import_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_node_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    bid_outline_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    template_library_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    search_vector: Mapped[str | None] = mapped_column(
        Text().with_variant(TSVECTOR(), "postgresql"),
        nullable=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        JSON().with_variant(Vector(1024), "postgresql"),
        nullable=True,
    )
    embedding_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[RetrievalIndexStatus] = mapped_column(
        Enum(RetrievalIndexStatus), nullable=False, default=RetrievalIndexStatus.published
    )
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
