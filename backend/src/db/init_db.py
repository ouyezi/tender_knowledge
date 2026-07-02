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
    image_extraction_cache,
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


def _sync_knowledge_chunk_retrieval_schema(conn) -> None:
    if conn.dialect.name != "postgresql":
        return
    conn.execute(
        text(
            """
            ALTER TABLE knowledge_chunks
            ADD COLUMN IF NOT EXISTS embedding_status varchar(20) NOT NULL DEFAULT 'pending'
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE knowledge_chunks
            ADD COLUMN IF NOT EXISTS indexed_at timestamptz
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE chunk_embeddings
            ADD COLUMN IF NOT EXISTS title_embedding vector(1024)
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE chunk_embeddings
            ADD COLUMN IF NOT EXISTS content_hash varchar(64)
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE chunk_assets
            ADD COLUMN IF NOT EXISTS extracted_facts jsonb
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE chunk_assets
            ADD COLUMN IF NOT EXISTS table_storage_url varchar(512)
            """
        )
    )


_KNOWLEDGE_CHUNK_DROP_COLUMNS = (
    # 20260628_1100 knowledge_chunk_field_trim
    "page_start",
    "page_end",
    "edit_distance_avg",
    "variables",
    "exclusion_rules",
    "need_parent_context",
    "winning_flag",
    "is_immutable",
    "issue_date",
    # 20260628_1200 knowledge_chunk_more_trim
    "industries",
    "customer_types",
    "parent_id",
    "project_name",
    "source_type",
    "retrieval_weight",
)


def _sync_knowledge_chunk_field_trim_schema(conn) -> None:
    if conn.dialect.name != "postgresql":
        return
    for col in _KNOWLEDGE_CHUNK_DROP_COLUMNS:
        conn.execute(
            text(
                f"""
                ALTER TABLE knowledge_chunks
                DROP COLUMN IF EXISTS {col}
                """
            )
        )


def _sync_qualification_info_schema(conn) -> None:
    if conn.dialect.name != "postgresql":
        return
    conn.execute(
        text(
            """
            ALTER TABLE knowledge_chunks
            ADD COLUMN IF NOT EXISTS qualification_info varchar(2048)
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE knowledge_chunks
            DROP COLUMN IF EXISTS certificate_number
            """
        )
    )
    conn.execute(
        text(
            """
            ALTER TABLE knowledge_chunks
            DROP COLUMN IF EXISTS certificate_date
            """
        )
    )


def init_db() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            _ensure_pgvector_extension(conn)
            _sync_knowledge_chunk_retrieval_schema(conn)
            _sync_knowledge_chunk_field_trim_schema(conn)
            _sync_qualification_info_schema(conn)
    Base.metadata.create_all(bind=engine)
