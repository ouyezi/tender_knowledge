from sqlalchemy import text

from src.db.session import Base, engine
from src.models import (  # noqa: F401
    actual_bid_parse_task,
    chunk_asset,
    chunk_embedding,
    document,
    document_media_asset,
    document_parse_suggestion,
    document_tree_node,
    downstream_task_entry,
    file_import,
    file_purpose_suggestion,
    import_audit_log,
    import_task,
    kb_clone_log,
    knowledge_base,
    knowledge_chunk,
)


def _ensure_pgvector_extension(conn) -> None:
    if conn.dialect.name != "postgresql":
        return
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def init_db() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            _ensure_pgvector_extension(conn)
    Base.metadata.create_all(bind=engine)
