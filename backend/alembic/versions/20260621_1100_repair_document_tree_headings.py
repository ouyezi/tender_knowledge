"""Repair document tree heading hierarchy from outline.json."""

from __future__ import annotations

from alembic import op

revision = "20260621_1100_repair_document_tree_headings"
down_revision = "20260621_1000_directory_blueprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from src.db.session import SessionLocal
    from src.services.doc_chunk.repair_document_tree_headings import repair_all_ready_document_trees

    db = SessionLocal()
    try:
        repair_all_ready_document_trees(db)
    finally:
        db.close()


def downgrade() -> None:
    pass
