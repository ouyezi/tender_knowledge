"""Apply knowledge_chunks taxonomy columns and seed knowledge_taxonomy (local dev)."""

from __future__ import annotations

from sqlalchemy import inspect, text

from src.db.session import engine
from src.models.knowledge_taxonomy import KnowledgeTaxonomy
from src.services.knowledge.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS

from e2e.reset_business_data import assert_database_url_is_safe


def _seed_knowledge_taxonomy(session) -> None:
    if session.query(KnowledgeTaxonomy).count() > 0:
        return
    for row in KNOWLEDGE_TAXONOMY_SEED_ROWS:
        session.add(
            KnowledgeTaxonomy(
                kb_id=None,
                dimension=row["dimension"],
                code=row["code"],
                parent_code=row["parent_code"],
                label=row["label"],
                label_en=row["label_en"],
                level=row["level"],
                sort_order=row["sort_order"],
                is_active=row["is_active"],
                metadata_json=row["metadata"],
            )
        )
    session.commit()


def _column_names(conn, table: str) -> set[str]:
    return {col["name"] for col in inspect(conn).get_columns(table)}


def apply_knowledge_taxonomy_schema() -> dict[str, object]:
    assert_database_url_is_safe()
    with engine.begin() as conn:
        cols = _column_names(conn, "knowledge_chunks")
        if "category" in cols:
            conn.execute(text("ALTER TABLE knowledge_chunks DROP COLUMN category"))
        if "quote_mode" in cols:
            conn.execute(text("ALTER TABLE knowledge_chunks DROP COLUMN quote_mode"))
        if "products" in cols:
            conn.execute(text("ALTER TABLE knowledge_chunks DROP COLUMN products"))

        cols = _column_names(conn, "knowledge_chunks")
        if "block_type_code" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE knowledge_chunks "
                    "ADD COLUMN block_type_code VARCHAR(64) NOT NULL DEFAULT 'product_solution'"
                )
            )
            conn.execute(
                text("ALTER TABLE knowledge_chunks ALTER COLUMN block_type_code DROP DEFAULT")
            )
        if "application_type_code" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE knowledge_chunks "
                    "ADD COLUMN application_type_code VARCHAR(64) NOT NULL DEFAULT 'preferred_reference'"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE knowledge_chunks ALTER COLUMN application_type_code DROP DEFAULT"
                )
            )
        if "business_line_codes" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE knowledge_chunks "
                    "ADD COLUMN business_line_codes JSONB NOT NULL DEFAULT '[\"general\"]'::jsonb"
                )
            )
            conn.execute(
                text("ALTER TABLE knowledge_chunks ALTER COLUMN business_line_codes DROP DEFAULT")
            )

        conn.execute(text("TRUNCATE knowledge_taxonomy RESTART IDENTITY CASCADE"))

    from sqlalchemy.orm import Session

    session = Session(engine)
    try:
        _seed_knowledge_taxonomy(session)
        seeded = session.query(KnowledgeTaxonomy).count()
    finally:
        session.close()

    return {"taxonomy_rows_seeded": seeded, "seed_source_rows": len(KNOWLEDGE_TAXONOMY_SEED_ROWS)}


if __name__ == "__main__":
    print(apply_knowledge_taxonomy_schema())
