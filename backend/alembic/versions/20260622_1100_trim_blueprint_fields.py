"""trim low-value blueprint fields

Revision ID: 20260622_1100
Revises: 20260622_1000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260622_1100"
down_revision: str | None = "20260622_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("knowledge_blueprints", "related_regulations")
    op.drop_column("knowledge_blueprints", "overall_strategy")
    op.drop_column("knowledge_blueprints", "common_mistakes")
    op.drop_column("knowledge_blueprints", "template_style")
    op.drop_column("knowledge_blueprints", "usual_page_range")

    op.drop_column("knowledge_blueprint_nodes", "purpose")
    op.drop_column("knowledge_blueprint_nodes", "writing_goal")
    op.drop_column("knowledge_blueprint_nodes", "writing_hint")
    op.drop_column("knowledge_blueprint_nodes", "content_type")
    op.drop_column("knowledge_blueprint_nodes", "keyword_hint")


def downgrade() -> None:
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("keyword_hint", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("content_type", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("writing_hint", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("writing_goal", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprint_nodes",
        sa.Column("purpose", sa.Text(), nullable=True),
    )

    op.add_column(
        "knowledge_blueprints",
        sa.Column("usual_page_range", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprints",
        sa.Column("template_style", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprints",
        sa.Column("common_mistakes", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprints",
        sa.Column("overall_strategy", sa.Text(), nullable=True),
    )
    op.add_column(
        "knowledge_blueprints",
        sa.Column("related_regulations", sa.JSON(), nullable=False, server_default="[]"),
    )
