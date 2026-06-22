"""blueprint generation extraction fields

Revision ID: 20260622_1000
Revises: 20260621_1200_widen_blueprint_text_fields
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260622_1000"
down_revision: str | None = "20260621_1200_widen_blueprint_text_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_blueprints",
        sa.Column("suggested_structure_md", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("content_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("tender_response_hint", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_blueprint_nodes", "tender_response_hint")
    op.drop_column("knowledge_blueprint_nodes", "content_description")
    op.drop_column("knowledge_blueprints", "suggested_structure_md")
