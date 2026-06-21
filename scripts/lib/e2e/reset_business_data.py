from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text

from src.config import Settings
from src.db.session import engine

BUSINESS_TABLES: tuple[str, ...] = (
    "chunk_embeddings",
    "chunk_assets",
    "knowledge_chunks",
    "knowledge_blueprint_nodes",
    "knowledge_blueprints",
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
)


def assert_database_url_is_safe(database_url: str | None = None) -> None:
    url = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge",
    )
    if url.startswith("sqlite"):
        return
    parsed = urlparse(url.replace("+psycopg", "").replace("+psycopg2", ""))
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if host not in {"127.0.0.1", "localhost"} or port not in {5433, None}:
        raise RuntimeError(f"refusing to reset non-local database: {host}:{port}")


def clear_storage_root(storage_root: Path | None = None) -> int:
    root = Path(storage_root or Settings().storage_root)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return 0
    removed = 0
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed


def reset_business_data(*, storage_root: Path | None = None) -> dict[str, int]:
    assert_database_url_is_safe()
    truncated = 0
    tables_sql = ", ".join(BUSINESS_TABLES)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tables_sql} RESTART IDENTITY CASCADE"))
        truncated = len(BUSINESS_TABLES)
    files_removed = clear_storage_root(storage_root)
    return {"tables_truncated": truncated, "storage_entries_removed": files_removed}
