"""epic6 generation assist foundation

Revision ID: 20260615_1000
Revises: 20260614_1500
Create Date: 2026-06-15 10:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260615_1000"
down_revision: str | None = "20260614_1500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


tender_requirement_status_enum = sa.Enum("active", "archived", name="tenderrequirementstatus")
generation_task_status_enum = sa.Enum(
    "pending", "running", "completed", "failed", name="generationtaskstatus"
)
draft_outcome_status_enum = sa.Enum(
    "pending", "accepted", "discarded", name="draftoutcomestatus"
)
module_assembly_suggestion_status_enum = sa.Enum(
    "draft", "adopted", "rejected", name="moduleassemblysuggestionstatus"
)


def upgrade() -> None:
    op.create_table(
        "tender_requirement_contexts",
        sa.Column("requirement_context_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column(
            "outline_structure",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "outline_nodes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "score_points",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "rejection_clauses",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "format_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "qualification_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "response_clauses",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("status", tender_requirement_status_enum, nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("requirement_context_id"),
    )
    op.create_index(
        "ix_tender_requirement_contexts_kb_status_created",
        "tender_requirement_contexts",
        ["kb_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tender_requirement_contexts_kb_id"),
        "tender_requirement_contexts",
        ["kb_id"],
        unique=False,
    )

    op.create_table(
        "prompt_config_versions",
        sa.Column("prompt_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version_tag", sa.String(length=64), nullable=False),
        sa.Column("template_system", sa.Text(), nullable=False),
        sa.Column("template_user", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("prompt_version_id"),
    )

    op.add_column(
        "module_assembly_suggestions",
        sa.Column("requirement_context_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "module_assembly_suggestions",
        sa.Column(
            "status",
            module_assembly_suggestion_status_enum,
            nullable=False,
            server_default="draft",
        ),
    )
    op.add_column(
        "module_assembly_suggestions",
        sa.Column("adoption_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "module_assembly_suggestions",
        sa.Column("adopted_by", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "module_assembly_suggestions",
        sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_module_assembly_suggestions_requirement_context_id",
        "module_assembly_suggestions",
        "tender_requirement_contexts",
        ["requirement_context_id"],
        ["requirement_context_id"],
    )

    op.create_table(
        "generation_tasks",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_context_id", sa.Uuid(), nullable=False),
        sa.Column("suggestion_id", sa.Uuid(), nullable=True),
        sa.Column("target_outline_node", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", generation_task_status_enum, nullable=False),
        sa.Column("request_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_context_id"],
            ["tender_requirement_contexts.requirement_context_id"],
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["module_assembly_suggestions.suggestion_id"],
        ),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index(
        "ix_generation_tasks_kb_status_created",
        "generation_tasks",
        ["kb_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_generation_tasks_kb_id"), "generation_tasks", ["kb_id"], unique=False)

    op.create_table(
        "generation_snapshots",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_context_id", sa.Uuid(), nullable=False),
        sa.Column(
            "requirement_context_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("suggestion_id", sa.Uuid(), nullable=True),
        sa.Column("suggestion_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("target_outline_node", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "used_ku_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "used_wiki_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "used_template_chapter_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "used_manual_asset_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "variable_inputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("retrieval_trace_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("result_version", sa.String(length=64), nullable=False),
        sa.Column(
            "conflict_hints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "missing_material_hints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "input_priority_layers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_context_id"],
            ["tender_requirement_contexts.requirement_context_id"],
        ),
        sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.task_id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(
        op.f("ix_generation_snapshots_kb_id"), "generation_snapshots", ["kb_id"], unique=False
    )

    op.create_table(
        "chapter_drafts",
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_context_id", sa.Uuid(), nullable=False),
        sa.Column("suggestion_id", sa.Uuid(), nullable=True),
        sa.Column("target_outline_node", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "paragraphs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "conflict_hints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "missing_material_hints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("outcome_status", draft_outcome_status_enum, nullable=False),
        sa.Column("outcome_by", sa.String(length=128), nullable=True),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version_tag", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["requirement_context_id"],
            ["tender_requirement_contexts.requirement_context_id"],
        ),
        sa.ForeignKeyConstraint(["snapshot_id"], ["generation_snapshots.snapshot_id"]),
        sa.ForeignKeyConstraint(["suggestion_id"], ["module_assembly_suggestions.suggestion_id"]),
        sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.task_id"]),
        sa.PrimaryKeyConstraint("draft_id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(op.f("ix_chapter_drafts_kb_id"), "chapter_drafts", ["kb_id"], unique=False)

    op.add_column("generation_tasks", sa.Column("draft_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_generation_tasks_draft_id",
        "generation_tasks",
        "chapter_drafts",
        ["draft_id"],
        ["draft_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_generation_tasks_draft_id", "generation_tasks", type_="foreignkey")
    op.drop_column("generation_tasks", "draft_id")
    op.drop_index(op.f("ix_chapter_drafts_kb_id"), table_name="chapter_drafts")
    op.drop_table("chapter_drafts")
    op.drop_index(op.f("ix_generation_snapshots_kb_id"), table_name="generation_snapshots")
    op.drop_table("generation_snapshots")
    op.drop_index(op.f("ix_generation_tasks_kb_id"), table_name="generation_tasks")
    op.drop_index("ix_generation_tasks_kb_status_created", table_name="generation_tasks")
    op.drop_table("generation_tasks")
    op.drop_constraint(
        "fk_module_assembly_suggestions_requirement_context_id",
        "module_assembly_suggestions",
        type_="foreignkey",
    )
    op.drop_column("module_assembly_suggestions", "adopted_at")
    op.drop_column("module_assembly_suggestions", "adopted_by")
    op.drop_column("module_assembly_suggestions", "adoption_reason")
    op.drop_column("module_assembly_suggestions", "status")
    op.drop_column("module_assembly_suggestions", "requirement_context_id")
    op.drop_table("prompt_config_versions")
    op.drop_index(
        op.f("ix_tender_requirement_contexts_kb_id"),
        table_name="tender_requirement_contexts",
    )
    op.drop_index(
        "ix_tender_requirement_contexts_kb_status_created",
        table_name="tender_requirement_contexts",
    )
    op.drop_table("tender_requirement_contexts")

    module_assembly_suggestion_status_enum.drop(op.get_bind(), checkfirst=True)
    draft_outcome_status_enum.drop(op.get_bind(), checkfirst=True)
    generation_task_status_enum.drop(op.get_bind(), checkfirst=True)
    tender_requirement_status_enum.drop(op.get_bind(), checkfirst=True)
