"""knowledge chunk qualification_info

Revision ID: 20260629_1000
Revises: 20260628_1200
Create Date: 2026-06-29 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260629_1000"
down_revision: str | None = "20260628_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("TRUNCATE knowledge_chunks CASCADE")
    else:
        op.execute("DELETE FROM knowledge_chunks")

    op.drop_column("knowledge_chunks", "certificate_number")
    op.drop_column("knowledge_chunks", "certificate_date")
    op.add_column(
        "knowledge_chunks",
        sa.Column("qualification_info", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "qualification_info")
    op.add_column(
        "knowledge_chunks",
        sa.Column("certificate_number", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("certificate_date", sa.String(length=512), nullable=True),
    )
