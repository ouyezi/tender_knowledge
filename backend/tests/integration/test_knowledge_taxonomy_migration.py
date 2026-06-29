from sqlalchemy import inspect

from src.models.knowledge_taxonomy import KnowledgeTaxonomy
from src.services.knowledge.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS
from tests.helpers.taxonomy_seed import seed_knowledge_taxonomy


def test_knowledge_taxonomy_table_seeded(db_session):
    seed_knowledge_taxonomy(db_session)
    count = db_session.query(KnowledgeTaxonomy).count()
    assert count == len(KNOWLEDGE_TAXONOMY_SEED_ROWS)


def test_knowledge_chunks_has_taxonomy_columns(db_session):
    columns = {col["name"] for col in inspect(db_session.bind).get_columns("knowledge_chunks")}
    assert "block_type_code" in columns
    assert "application_type_code" in columns
    assert "business_line_codes" in columns
    assert "category" not in columns
    assert "quote_mode" not in columns
    assert "products" not in columns
