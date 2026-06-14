"""document media assets

Revision ID: 20260614_1600
Revises: 20260615_1000
Create Date: 2026-06-14 16:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260614_1600"
down_revision: str | None = "20260615_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_media_assets",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("source_block_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"]),
        sa.PrimaryKeyConstraint("asset_id"),
    )
    op.create_index(
        op.f("ix_document_media_assets_kb_id"),
        "document_media_assets",
        ["kb_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_media_assets_kb_doc",
        "document_media_assets",
        ["kb_id", "document_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_media_assets_kb_doc", table_name="document_media_assets")
    op.drop_index(op.f("ix_document_media_assets_kb_id"), table_name="document_media_assets")
    op.drop_table("document_media_assets")
