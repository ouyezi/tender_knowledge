"""add template_file to documentsourcetype

Revision ID: 20260618_1100
Revises: 20260618_1000
Create Date: 2026-06-18 11:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260618_1100"
down_revision: str | None = "20260618_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE documentsourcetype ADD VALUE IF NOT EXISTS 'template_file'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values safely; no-op.
    pass
