"""blueprint embeddings for semantic search

Revision ID: 20260622_1200
Revises: 20260622_1100
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260622_1200"
down_revision: str | None = "20260622_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "blueprint_embeddings",
        sa.Column("blueprint_id", sa.Uuid(), nullable=False),
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
            ["blueprint_id"], ["knowledge_blueprints.blueprint_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("blueprint_id"),
    )
    op.create_index("ix_blueprint_embeddings_kb_id", "blueprint_embeddings", ["kb_id"])


def downgrade() -> None:
    op.drop_index("ix_blueprint_embeddings_kb_id", table_name="blueprint_embeddings")
    op.drop_table("blueprint_embeddings")
