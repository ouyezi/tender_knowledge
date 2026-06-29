"""knowledge chunk field trim

Revision ID: 20260628_1100
Revises: 20260628_1000
Create Date: 2026-06-28 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260628_1100"
down_revision: str | None = "20260628_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROP_COLUMNS = (
    "page_start",
    "page_end",
    "edit_distance_avg",
    "variables",
    "exclusion_rules",
    "need_parent_context",
    "winning_flag",
    "is_immutable",
    "issue_date",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("TRUNCATE knowledge_chunks CASCADE")
    else:
        op.execute("DELETE FROM knowledge_chunks")

    for col in _DROP_COLUMNS:
        op.drop_column("knowledge_chunks", col)

    op.add_column(
        "knowledge_chunks",
        sa.Column("certificate_date", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("certificate_number", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "certificate_number")
    op.drop_column("knowledge_chunks", "certificate_date")

    op.add_column("knowledge_chunks", sa.Column("issue_date", sa.Date(), nullable=True))
    op.add_column(
        "knowledge_chunks",
        sa.Column("is_immutable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("winning_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("need_parent_context", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "exclusion_rules",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "variables",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column("knowledge_chunks", sa.Column("edit_distance_avg", sa.Float(), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.add_column("knowledge_chunks", sa.Column("page_start", sa.Integer(), nullable=True))
