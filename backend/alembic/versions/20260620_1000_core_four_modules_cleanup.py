"""core four modules cleanup - drop legacy tables

Revision ID: 20260620_1000
Revises: 20260618_1100
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260620_1000"
down_revision: str | None = "20260618_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_TABLES: tuple[str, ...] = (
    "retrieval_feedbacks",
    "retrieval_traces",
    "retrieval_index_entries",
    "retrieval_eval_cases",
    "retrieval_eval_runs",
    "retrieval_eval_sets",
    "retrieval_strategy_versions",
    "candidate_confirm_audit_logs",
    "candidate_knowledge_stubs",
    "candidate_knowledges",
    "knowledge_units",
    "wikis",
    "manual_assets",
    "bid_outline_structure_diffs",
    "bid_outline_nodes",
    "bid_outlines",
    "actual_bid_audit_logs",
    "template_audit_logs",
    "template_structure_diffs",
    "template_publish_snapshots",
    "template_parse_suggestions",
    "template_parse_tasks",
    "template_materials",
    "template_variables",
    "template_rules",
    "template_chapters",
    "templates",
    "template_libraries",
    "generation_snapshots",
    "generation_tasks",
    "chapter_drafts",
    "module_assembly_suggestions",
    "tender_requirement_contexts",
    "chapter_pattern_mining_tasks",
    "chapter_patterns",
    "classification_audit_logs",
    "classification_references",
    "product_categories",
    "chapter_taxonomies",
    "prompt_config_versions",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in LEGACY_TABLES:
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

        op.drop_column("file_imports", "product_category_ids")
        op.drop_column("file_imports", "chapter_taxonomy_id")
        op.drop_column("file_imports", "target_object_type")
        op.drop_column("documents", "product_category_ids")
        op.drop_column("document_tree_nodes", "chapter_taxonomy_id")
        op.drop_column("document_tree_nodes", "product_category_ids")
        op.drop_column("file_purpose_suggestions", "suggested_product_category_ids")
        op.drop_column("file_purpose_suggestions", "suggested_chapter_taxonomy_id")


def downgrade() -> None:
    raise NotImplementedError("Irreversible cleanup migration")
