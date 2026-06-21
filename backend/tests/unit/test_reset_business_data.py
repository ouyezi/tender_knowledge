import pytest

from e2e.reset_business_data import assert_database_url_is_safe, BUSINESS_TABLES


def test_assert_database_url_is_safe_allows_local_postgres():
    assert_database_url_is_safe("postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge")


def test_assert_database_url_is_safe_rejects_remote():
    with pytest.raises(RuntimeError, match="refusing to reset"):
        assert_database_url_is_safe("postgresql+psycopg://user:pass@prod.example.com:5432/db")


def test_business_tables_match_retained_schema():
    retained = {
        "chunk_embeddings",
        "chunk_assets",
        "knowledge_chunks",
        "document_media_assets",
        "document_parse_suggestions",
        "document_tree_nodes",
        "documents",
        "actual_bid_parse_tasks",
        "downstream_task_entries",
        "import_audit_logs",
        "import_tasks",
        "file_purpose_suggestions",
        "file_imports",
        "kb_clone_logs",
    }
    assert set(BUSINESS_TABLES) == retained


def test_business_tables_excludes_knowledge_bases():
    assert "knowledge_bases" not in BUSINESS_TABLES
