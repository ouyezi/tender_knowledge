import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ModuleAssemblySuggestion(Base):
    __tablename__ = "module_assembly_suggestions"
    __table_args__ = (
        Index("ix_module_assembly_suggestions_kb_trace", "kb_id", "trace_id"),
    )

    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("retrieval_traces.trace_id"), nullable=False
    )
    target_outline_node: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    suggested_template_chapter_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    suggested_ku_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    suggested_wiki_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    suggested_manual_asset_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    suggested_bid_outline_node_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    suggested_chapter_pattern_ids: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list
    )
    organization_hint: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_rate: Mapped[float] = mapped_column(Float, nullable=False)
    score_detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    score_point_coverage: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    rejection_risks: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    risk_flags: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    hit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_pack_snapshot: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    project_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tender_context_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
