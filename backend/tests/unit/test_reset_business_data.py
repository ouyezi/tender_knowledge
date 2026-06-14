import pytest

from e2e.reset_business_data import assert_database_url_is_safe, BUSINESS_TABLES


def test_assert_database_url_is_safe_allows_local_postgres():
    assert_database_url_is_safe("postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge")


def test_assert_database_url_is_safe_rejects_remote():
    with pytest.raises(RuntimeError, match="refusing to reset"):
        assert_database_url_is_safe("postgresql+psycopg://user:pass@prod.example.com:5432/db")


def test_business_tables_includes_file_imports():
    assert "file_imports" in BUSINESS_TABLES
    assert "knowledge_units" in BUSINESS_TABLES


def test_business_tables_excludes_knowledge_bases():
    assert "knowledge_bases" not in BUSINESS_TABLES
    assert "chapter_taxonomies" not in BUSINESS_TABLES
