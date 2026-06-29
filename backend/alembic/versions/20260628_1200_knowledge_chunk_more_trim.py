"""knowledge chunk more field trim

Revision ID: 20260628_1200
Revises: 20260628_1100
Create Date: 2026-06-28 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260628_1200"
down_revision: str | None = "20260628_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_COLUMNS = (
    "industries",
    "customer_types",
    "parent_id",
    "project_name",
    "source_type",
    "retrieval_weight",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("TRUNCATE knowledge_chunks CASCADE")
    else:
        op.execute("DELETE FROM knowledge_chunks")

    for col in _DROP_COLUMNS:
        op.drop_column("knowledge_chunks", col)


def downgrade() -> None:
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "retrieval_weight",
            sa.Numeric(4, 2),
            nullable=False,
            server_default="1.00",
        ),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="bid"),
    )
    op.add_column("knowledge_chunks", sa.Column("project_name", sa.String(length=255), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("parent_id", sa.BigInteger(), nullable=True))
    op.add_column(
        "knowledge_chunks",
        sa.Column("customer_types", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("industries", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
