"""epic5 retrieval foundation

Revision ID: 20260614_1500
Revises:
Create Date: 2026-06-14 15:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260614_1500"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


retrieval_object_type_enum = sa.Enum(
    "ku",
    "wiki",
    "template",
    "template_chapter",
    "bid_outline",
    "bid_outline_node",
    "chapter_pattern",
    "manual_asset",
    name="retrievalobjecttype",
)
retrieval_index_status_enum = sa.Enum(
    "published", "deprecated", name="retrievalindexstatus"
)
retrieval_intent_enum = sa.Enum(
    "knowledge_lookup",
    "material_recommend",
    "module_suggestion",
    "trace_lookup",
    "directory_match",
    name="retrievalintent",
)
retrieval_trace_status_enum = sa.Enum("success", "partial", "failed", name="retrievaltracestatus")
retrieval_feedback_type_enum = sa.Enum(
    "click",
    "adopt",
    "copy",
    "add_to_draft",
    "useful",
    "not_useful",
    "false_positive",
    "false_negative",
    name="retrievalfeedbacktype",
)
retrieval_eval_set_status_enum = sa.Enum(
    "draft", "active", "archived", name="retrievalevalsetstatus"
)
retrieval_eval_case_created_from_enum = sa.Enum(
    "manual", "user_feedback", "production_log", name="retrievalevalcasecreatedfrom"
)
retrieval_eval_case_status_enum = sa.Enum(
    "pending", "confirmed", "rejected", name="retrievalevalcasestatus"
)
retrieval_eval_run_status_enum = sa.Enum(
    "running", "success", "failed", name="retrievalevalrunstatus"
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "retrieval_strategy_versions",
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding_config_version", sa.String(length=64), nullable=True),
        sa.Column("rerank_config_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_config_version", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("strategy_version_id"),
    )
    op.create_index(
        "ix_retrieval_strategy_versions_kb_active",
        "retrieval_strategy_versions",
        ["kb_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "retrieval_index_entries",
        sa.Column("index_entry_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("object_type", retrieval_object_type_enum, nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("product_category_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("chapter_taxonomy_id", sa.Uuid(), nullable=True),
        sa.Column("knowledge_type", sa.String(length=64), nullable=True),
        sa.Column("file_purpose", sa.String(length=64), nullable=True),
        sa.Column("import_id", sa.Uuid(), nullable=True),
        sa.Column("source_doc_id", sa.Uuid(), nullable=True),
        sa.Column("source_node_id", sa.Uuid(), nullable=True),
        sa.Column("bid_outline_id", sa.Uuid(), nullable=True),
        sa.Column("template_library_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("embedding", Vector(dim=1024), nullable=True),
        sa.Column("embedding_config_version", sa.String(length=64), nullable=True),
        sa.Column("status", retrieval_index_status_enum, nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("index_entry_id"),
        sa.UniqueConstraint(
            "kb_id", "object_type", "object_id", name="uq_retrieval_index_entries_kb_object"
        ),
    )
    op.create_index(
        "ix_retrieval_index_entries_kb_type_status",
        "retrieval_index_entries",
        ["kb_id", "object_type", "status"],
        unique=False,
    )
    op.create_index(
        "ix_retrieval_index_entries_search_vector",
        "retrieval_index_entries",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_retrieval_index_entries_embedding",
        "retrieval_index_entries",
        ["embedding"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "retrieval_traces",
        sa.Column("trace_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("intent", retrieval_intent_enum, nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("request_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("response_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("stages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", retrieval_trace_status_enum, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("operator_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"],
            ["retrieval_strategy_versions.strategy_version_id"],
        ),
        sa.PrimaryKeyConstraint("trace_id"),
    )
    op.create_index(
        "ix_retrieval_traces_kb_intent_created",
        "retrieval_traces",
        ["kb_id", "intent", "created_at"],
        unique=False,
    )

    op.create_table(
        "retrieval_feedbacks",
        sa.Column("feedback_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_type", retrieval_feedback_type_enum, nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=True),
        sa.Column("object_id", sa.Uuid(), nullable=True),
        sa.Column("rank_position", sa.Integer(), nullable=True),
        sa.Column("expected_object_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("filter_adjustment", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("operator_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trace_id"], ["retrieval_traces.trace_id"]),
        sa.PrimaryKeyConstraint("feedback_id"),
    )

    op.create_table(
        "retrieval_eval_sets",
        sa.Column("eval_set_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", retrieval_eval_set_status_enum, nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("eval_set_id"),
    )

    op.create_table(
        "retrieval_eval_cases",
        sa.Column("eval_case_id", sa.Uuid(), nullable=False),
        sa.Column("eval_set_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("intent", retrieval_intent_enum, nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_object_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("negative_object_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("product_category_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("chapter_taxonomy_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_from", retrieval_eval_case_created_from_enum, nullable=False),
        sa.Column("source_feedback_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.String(length=128), nullable=True),
        sa.Column("status", retrieval_eval_case_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["eval_set_id"], ["retrieval_eval_sets.eval_set_id"]),
        sa.ForeignKeyConstraint(["source_feedback_id"], ["retrieval_feedbacks.feedback_id"]),
        sa.PrimaryKeyConstraint("eval_case_id"),
    )

    op.create_table(
        "retrieval_eval_runs",
        sa.Column("eval_run_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("eval_set_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("comparison_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", retrieval_eval_run_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["eval_set_id"], ["retrieval_eval_sets.eval_set_id"]),
        sa.ForeignKeyConstraint(
            ["strategy_version_id"],
            ["retrieval_strategy_versions.strategy_version_id"],
        ),
        sa.ForeignKeyConstraint(
            ["baseline_strategy_version_id"],
            ["retrieval_strategy_versions.strategy_version_id"],
        ),
        sa.PrimaryKeyConstraint("eval_run_id"),
    )

    op.create_table(
        "module_assembly_suggestions",
        sa.Column("suggestion_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.Uuid(), nullable=False),
        sa.Column("target_outline_node", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "suggested_template_chapter_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("suggested_ku_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("suggested_wiki_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "suggested_manual_asset_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "suggested_bid_outline_node_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "suggested_chapter_pattern_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("organization_hint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("coverage_rate", sa.Float(), nullable=False),
        sa.Column("score_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score_point_coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rejection_risks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hit_reason", sa.Text(), nullable=True),
        sa.Column("knowledge_pack_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("product_category_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("project_type", sa.String(length=64), nullable=True),
        sa.Column("customer_type", sa.String(length=64), nullable=True),
        sa.Column("tender_context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trace_id"], ["retrieval_traces.trace_id"]),
        sa.PrimaryKeyConstraint("suggestion_id"),
    )
    op.create_index(
        "ix_module_assembly_suggestions_kb_trace",
        "module_assembly_suggestions",
        ["kb_id", "trace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_module_assembly_suggestions_kb_trace", table_name="module_assembly_suggestions"
    )
    op.drop_table("module_assembly_suggestions")
    op.drop_table("retrieval_eval_runs")
    op.drop_table("retrieval_eval_cases")
    op.drop_table("retrieval_eval_sets")
    op.drop_table("retrieval_feedbacks")
    op.drop_index("ix_retrieval_traces_kb_intent_created", table_name="retrieval_traces")
    op.drop_table("retrieval_traces")
    op.drop_index("ix_retrieval_index_entries_embedding", table_name="retrieval_index_entries")
    op.drop_index(
        "ix_retrieval_index_entries_search_vector", table_name="retrieval_index_entries"
    )
    op.drop_index(
        "ix_retrieval_index_entries_kb_type_status", table_name="retrieval_index_entries"
    )
    op.drop_table("retrieval_index_entries")
    op.drop_index(
        "ix_retrieval_strategy_versions_kb_active", table_name="retrieval_strategy_versions"
    )
    op.drop_table("retrieval_strategy_versions")

    retrieval_eval_run_status_enum.drop(op.get_bind(), checkfirst=True)
    retrieval_eval_case_status_enum.drop(op.get_bind(), checkfirst=True)
    retrieval_eval_case_created_from_enum.drop(op.get_bind(), checkfirst=True)
    retrieval_eval_set_status_enum.drop(op.get_bind(), checkfirst=True)
    retrieval_feedback_type_enum.drop(op.get_bind(), checkfirst=True)
    retrieval_trace_status_enum.drop(op.get_bind(), checkfirst=True)
    retrieval_intent_enum.drop(op.get_bind(), checkfirst=True)
    retrieval_index_status_enum.drop(op.get_bind(), checkfirst=True)
    retrieval_object_type_enum.drop(op.get_bind(), checkfirst=True)
