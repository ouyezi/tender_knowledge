"""chunk_assets table_storage_url for table docx slices

Revision ID: 20260701_1000
Revises: 20260629_1000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_1000"
down_revision: str | None = "20260629_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chunk_assets",
        sa.Column("table_storage_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chunk_assets", "table_storage_url")
