"""writing techniques tables

Revision ID: 20260626_1000
Revises: 20260623_1000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260626_1000"
down_revision: str | None = "20260623_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "writing_techniques",
        sa.Column("technique_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("applicable_scene", sa.Text(), nullable=True),
        sa.Column("writing_summary", sa.Text(), nullable=True),
        sa.Column(
            "applicable_sections",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("usage_mode", sa.String(length=20), nullable=False),
        sa.Column("recommended_outline", sa.Text(), nullable=True),
        sa.Column("writing_strategy", sa.Text(), nullable=True),
        sa.Column("must_include", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("output_requirement", sa.Text(), nullable=True),
        sa.Column("checklist", sa.Text(), nullable=True),
        sa.Column("confidence", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("source_chunk_id", sa.BigInteger(), nullable=True),
        sa.Column("source_invalid", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
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
        sa.ForeignKeyConstraint(["source_chunk_id"], ["knowledge_chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("technique_id"),
    )
    op.create_index("ix_writing_techniques_kb_id", "writing_techniques", ["kb_id"])
    op.create_index("ix_writing_techniques_kb_status", "writing_techniques", ["kb_id", "status"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_writing_techniques_kb_source_chunk
        ON writing_techniques (kb_id, source_chunk_id)
        WHERE source_chunk_id IS NOT NULL
        """
    )

    op.create_table(
        "writing_technique_embeddings",
        sa.Column("technique_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "embedding_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["technique_id"], ["writing_techniques.technique_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("technique_id"),
    )
    op.create_index(
        "ix_writing_technique_embeddings_kb_id",
        "writing_technique_embeddings",
        ["kb_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_writing_technique_embeddings_kb_id", table_name="writing_technique_embeddings")
    op.drop_table("writing_technique_embeddings")
    op.execute("DROP INDEX IF EXISTS uq_writing_techniques_kb_source_chunk")
    op.drop_index("ix_writing_techniques_kb_status", table_name="writing_techniques")
    op.drop_index("ix_writing_techniques_kb_id", table_name="writing_techniques")
    op.drop_table("writing_techniques")
