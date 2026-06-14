import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base
from src.models.candidate_knowledge import CandidateKnowledgeType


class CandidateKnowledgeStubStatus(str, enum.Enum):
    pending_confirm = "pending_confirm"
    confirmed = "confirmed"
    rejected = "rejected"
    merged = "merged"
    published = "published"


class CandidateKnowledgeStub(Base):
    __tablename__ = "candidate_knowledge_stubs"

    stub_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    import_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("templates.template_id"), nullable=False
    )
    template_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_chapters.template_chapter_id"), nullable=True
    )
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("template_materials.material_id"), nullable=True
    )
    candidate_type: Mapped[CandidateKnowledgeType] = mapped_column(
        Enum(CandidateKnowledgeType), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_category_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chapter_taxonomies.taxonomy_id"), nullable=True
    )
    suggested_knowledge_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suggestion_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    chunk_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[CandidateKnowledgeStubStatus] = mapped_column(
        Enum(CandidateKnowledgeStubStatus),
        nullable=False,
        default=CandidateKnowledgeStubStatus.pending_confirm,
    )
    epic4_batch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    confirmed_object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_object_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    searchable: Mapped[bool | None] = mapped_column(nullable=True)
    usage_hint: Mapped[str | None] = mapped_column(String(256), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    split_from_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    lineage: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    last_publish_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
