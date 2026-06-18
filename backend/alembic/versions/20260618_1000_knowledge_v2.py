"""knowledge v2 tables

Revision ID: 20260618_1000
Revises: 20260614_1600
Create Date: 2026-06-18 10:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260618_1000"
down_revision: str | None = "20260614_1600"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_code", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("previous_version_id", sa.BigInteger(), nullable=True),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("knowledge_type", sa.String(length=32), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False, server_default="text"),
        sa.Column("doc_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("project_name", sa.String(length=255), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("catalog_path", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("primary_node_id", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "need_parent_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("quote_mode", sa.String(length=32), nullable=False, server_default="full"),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("products", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("industries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("customer_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expire_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("template_type", sa.String(length=32), nullable=True),
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("exclusion_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "retrieval_weight",
            sa.Numeric(precision=4, scale=2),
            nullable=False,
            server_default="1.00",
        ),
        sa.Column(
            "security_level",
            sa.String(length=32),
            nullable=False,
            server_default="internal",
        ),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="approved",
        ),
        sa.Column("winning_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("edit_distance_avg", sa.REAL(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_children", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("children_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_chunks_kb_id"), "knowledge_chunks", ["kb_id"], unique=False)
    op.create_index(
        op.f("ix_knowledge_chunks_doc_id"), "knowledge_chunks", ["doc_id"], unique=False
    )
    op.create_index(
        "uq_knowledge_chunks_latest_node",
        "knowledge_chunks",
        ["kb_id", "doc_id", "primary_node_id"],
        unique=True,
        postgresql_where=sa.text("is_latest = true"),
    )

    op.create_table(
        "chunk_assets",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("doc_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=True),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("asset_code", sa.String(length=64), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("raw_markdown", sa.Text(), nullable=True),
        sa.Column("llm_summary", sa.Text(), nullable=True),
        sa.Column("table_summary", sa.Text(), nullable=True),
        sa.Column("table_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("table_headers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("table_rows", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("table_type", sa.String(length=64), nullable=True),
        sa.Column("allow_row_filter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("image_type", sa.String(length=64), nullable=True),
        sa.Column("image_storage_url", sa.String(length=512), nullable=True),
        sa.Column("image_caption", sa.Text(), nullable=True),
        sa.Column("image_ocr_text", sa.Text(), nullable=True),
        sa.Column("required_with_text", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position_hint", sa.String(length=32), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chunk_assets_kb_id"), "chunk_assets", ["kb_id"], unique=False)
    op.create_index(op.f("ix_chunk_assets_doc_id"), "chunk_assets", ["doc_id"], unique=False)
    op.create_index(op.f("ix_chunk_assets_chunk_id"), "chunk_assets", ["chunk_id"], unique=False)
    op.create_index(
        "ix_chunk_assets_doc_range",
        "chunk_assets",
        ["kb_id", "doc_id", "char_start", "char_end"],
        unique=False,
    )

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("object_type", sa.String(length=16), nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("content_embedding", Vector(dim=1024), nullable=True),
        sa.Column("summary_embedding", Vector(dim=1024), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_type", "object_id", name="uq_chunk_embeddings_object"),
    )


def downgrade() -> None:
    op.drop_table("chunk_embeddings")
    op.drop_index("ix_chunk_assets_doc_range", table_name="chunk_assets")
    op.drop_index(op.f("ix_chunk_assets_chunk_id"), table_name="chunk_assets")
    op.drop_index(op.f("ix_chunk_assets_doc_id"), table_name="chunk_assets")
    op.drop_index(op.f("ix_chunk_assets_kb_id"), table_name="chunk_assets")
    op.drop_table("chunk_assets")
    op.drop_index("uq_knowledge_chunks_latest_node", table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_doc_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_kb_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
