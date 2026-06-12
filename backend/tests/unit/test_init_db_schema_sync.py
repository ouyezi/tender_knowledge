from unittest.mock import MagicMock

from src.db.init_db import _sync_missing_columns


def test_sync_missing_columns_adds_llm_progress():
    conn = MagicMock()
    _sync_missing_columns(conn)
    conn.execute.assert_called_once()
    sql = str(conn.execute.call_args[0][0])
    assert "template_parse_tasks" in sql
    assert "llm_progress" in sql
    assert "IF NOT EXISTS" in sql
