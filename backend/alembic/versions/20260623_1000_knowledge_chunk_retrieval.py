"""knowledge chunk retrieval: embedding status, title embedding, image cache

Revision ID: 20260623_1000
Revises: 20260622_1200
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260623_1000"
down_revision: str | None = "20260622_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "embedding_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "chunk_embeddings",
        sa.Column("title_embedding", Vector(1024), nullable=True),
    )
    op.add_column(
        "chunk_embeddings",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "chunk_assets",
        sa.Column("extracted_facts", sa.JSON(), nullable=True),
    )
    op.create_table(
        "image_extraction_cache",
        sa.Column("md5_hash", sa.String(length=32), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("extracted_facts", sa.JSON(), nullable=True),
        sa.Column("vision_model", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("md5_hash"),
    )


def downgrade() -> None:
    op.drop_table("image_extraction_cache")
    op.drop_column("chunk_assets", "extracted_facts")
    op.drop_column("chunk_embeddings", "content_hash")
    op.drop_column("chunk_embeddings", "title_embedding")
    op.drop_column("knowledge_chunks", "indexed_at")
    op.drop_column("knowledge_chunks", "embedding_status")
