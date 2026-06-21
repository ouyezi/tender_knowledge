"""Widen blueprint text fields for LLM-generated content."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260621_1200_widen_blueprint_text_fields"
down_revision = "20260621_1100_repair_document_tree_headings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "knowledge_blueprints",
        "template_style",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "knowledge_blueprints",
        "usual_page_range",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "knowledge_blueprint_nodes",
        "content_type",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "knowledge_blueprint_nodes",
        "content_type",
        existing_type=sa.Text(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "knowledge_blueprints",
        "usual_page_range",
        existing_type=sa.Text(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.alter_column(
        "knowledge_blueprints",
        "template_style",
        existing_type=sa.Text(),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
