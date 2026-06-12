import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class CandidateKnowledgeType(str, enum.Enum):
    ku = "ku"
    wiki = "wiki"
    chapter_pattern = "chapter_pattern"
    ignore = "ignore"


class CandidateKnowledgeStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"
    merged = "merged"
    published = "published"


class CandidateKnowledge(Base):
    __tablename__ = "candidate_knowledges"
    __table_args__ = (
        Index("ix_candidate_knowledges_kb_status_created", "kb_id", "status", "created_at"),
        Index("ix_candidate_knowledges_kb_import", "kb_id", "import_id"),
        Index(
            "ix_candidate_knowledges_source_doc_node",
            "source_doc_id",
            "source_node_id",
        ),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    source_doc_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.document_id"), nullable=False
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_tree_nodes.node_id"), nullable=False
    )
    candidate_type: Mapped[CandidateKnowledgeType] = mapped_column(
        Enum(CandidateKnowledgeType), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_knowledge_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suggested_chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    suggested_product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggestion_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[CandidateKnowledgeStatus] = mapped_column(
        Enum(CandidateKnowledgeStatus), nullable=False, default=CandidateKnowledgeStatus.pending
    )
    parse_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("actual_bid_parse_tasks.parse_task_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
