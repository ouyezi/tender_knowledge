"""knowledge taxonomy and dynamic knowledge

Revision ID: 20260628_1000
Revises: 20260626_1000
Create Date: 2026-06-28 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from src.services.knowledge.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS

revision: str = "20260628_1000"
down_revision: str | None = "20260626_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_taxonomy",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=True),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("parent_code", sa.String(length=64), nullable=True),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("label_en", sa.String(length=128), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("level IN (1, 2)", name="ck_knowledge_taxonomy_level"),
    )
    op.create_index(
        "uq_knowledge_taxonomy_dimension_code",
        "knowledge_taxonomy",
        ["dimension", "code"],
        unique=True,
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("TRUNCATE knowledge_chunks CASCADE")
    else:
        op.execute("DELETE FROM knowledge_chunks")

    op.drop_column("knowledge_chunks", "category")
    op.drop_column("knowledge_chunks", "quote_mode")
    op.drop_column("knowledge_chunks", "products")
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "block_type_code",
            sa.String(length=64),
            nullable=False,
            server_default="product_solution",
        ),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "application_type_code",
            sa.String(length=64),
            nullable=False,
            server_default="preferred_reference",
        ),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "business_line_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"general\"]'::jsonb"),
        ),
    )
    op.alter_column("knowledge_chunks", "block_type_code", server_default=None)
    op.alter_column("knowledge_chunks", "application_type_code", server_default=None)

    op.create_index(
        "ix_knowledge_chunks_block_type",
        "knowledge_chunks",
        ["kb_id", "block_type_code"],
    )
    op.create_index(
        "ix_knowledge_chunks_application_type",
        "knowledge_chunks",
        ["kb_id", "application_type_code"],
    )
    op.create_index(
        "ix_knowledge_chunks_business_lines",
        "knowledge_chunks",
        ["business_line_codes"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_knowledge_chunks_expire_date",
        "knowledge_chunks",
        ["kb_id", "expire_date"],
    )

    op.create_table(
        "dynamic_knowledge_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("dynamic_type_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "structured_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "business_line_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[\"general\"]'::jsonb"),
        ),
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=False,
            server_default="extracted",
        ),
        sa.Column("source_doc_id", sa.Uuid(), nullable=True),
        sa.Column("source_chunk_id", sa.BigInteger(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expire_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column(
            "sync_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "create_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "update_time",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dynamic_knowledge_kb_type",
        "dynamic_knowledge_records",
        ["kb_id", "dynamic_type_code"],
    )
    op.create_index(
        "ix_dynamic_knowledge_kb_status",
        "dynamic_knowledge_records",
        ["kb_id", "status"],
    )
    op.create_index(
        "ix_dynamic_knowledge_expire",
        "dynamic_knowledge_records",
        ["kb_id", "expire_date"],
    )
    op.create_index(
        "ix_dynamic_knowledge_business_lines",
        "dynamic_knowledge_records",
        ["business_line_codes"],
        postgresql_using="gin",
    )

    taxonomy_table = sa.table(
        "knowledge_taxonomy",
        sa.column("kb_id", sa.Uuid()),
        sa.column("dimension", sa.String()),
        sa.column("code", sa.String()),
        sa.column("parent_code", sa.String()),
        sa.column("label", sa.String()),
        sa.column("label_en", sa.String()),
        sa.column("level", sa.SmallInteger()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
        sa.column("metadata", postgresql.JSONB()),
    )
    rows = [
        {
            "kb_id": None,
            "dimension": row["dimension"],
            "code": row["code"],
            "parent_code": row["parent_code"],
            "label": row["label"],
            "label_en": row["label_en"],
            "level": row["level"],
            "sort_order": row["sort_order"],
            "is_active": row["is_active"],
            "metadata": row["metadata"],
        }
        for row in KNOWLEDGE_TAXONOMY_SEED_ROWS
    ]
    op.bulk_insert(taxonomy_table, rows)


def downgrade() -> None:
    op.drop_table("dynamic_knowledge_records")
    op.drop_index("ix_knowledge_chunks_expire_date", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_business_lines", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_application_type", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_block_type", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "business_line_codes")
    op.drop_column("knowledge_chunks", "application_type_code")
    op.drop_column("knowledge_chunks", "block_type_code")
    op.add_column(
        "knowledge_chunks",
        sa.Column("products", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("category", sa.String(length=64), nullable=False, server_default="technical"),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("quote_mode", sa.String(length=32), nullable=False, server_default="full"),
    )
    op.drop_table("knowledge_taxonomy")
