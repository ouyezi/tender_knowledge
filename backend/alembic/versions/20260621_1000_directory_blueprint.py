"""directory blueprint tables

Revision ID: 20260621_1000
Revises: 20260620_1000
Create Date: 2026-06-21 10:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260621_1000"
down_revision: str | None = "20260620_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_blueprints",
        sa.Column("blueprint_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_doc_id", sa.Uuid(), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("source_chapter_title", sa.String(length=200), nullable=True),
        sa.Column(
            "product_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "industry_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "scenario_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "applicable_project_type",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "related_regulations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("overall_strategy", sa.Text(), nullable=True),
        sa.Column("common_mistakes", sa.Text(), nullable=True),
        sa.Column("template_style", sa.String(length=50), nullable=True),
        sa.Column("usual_page_range", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("blueprint_id"),
        sa.UniqueConstraint("kb_id", "source_node_id", name="uq_blueprints_kb_source_node"),
    )
    op.create_index(
        "ix_knowledge_blueprints_kb_id",
        "knowledge_blueprints",
        ["kb_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_blueprint_nodes",
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("blueprint_id", sa.Uuid(), nullable=False),
        sa.Column("parent_node_id", sa.Uuid(), nullable=True),
        sa.Column("node_code", sa.String(length=50), nullable=True),
        sa.Column("node_title", sa.String(length=200), nullable=False),
        sa.Column("node_level", sa.Integer(), nullable=False),
        sa.Column("node_order", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("writing_goal", sa.Text(), nullable=True),
        sa.Column("writing_hint", sa.Text(), nullable=True),
        sa.Column("importance_level", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=True),
        sa.Column(
            "keyword_hint",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["blueprint_id"],
            ["knowledge_blueprints.blueprint_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_node_id"],
            ["knowledge_blueprint_nodes.node_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("node_id"),
    )
    op.create_index(
        "ix_knowledge_blueprint_nodes_blueprint_id",
        "knowledge_blueprint_nodes",
        ["blueprint_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_blueprint_nodes_parent_node_id",
        "knowledge_blueprint_nodes",
        ["parent_node_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_blueprint_nodes_parent_node_id",
        table_name="knowledge_blueprint_nodes",
    )
    op.drop_index(
        "ix_knowledge_blueprint_nodes_blueprint_id",
        table_name="knowledge_blueprint_nodes",
    )
    op.drop_table("knowledge_blueprint_nodes")
    op.drop_index("ix_knowledge_blueprints_kb_id", table_name="knowledge_blueprints")
    op.drop_table("knowledge_blueprints")
