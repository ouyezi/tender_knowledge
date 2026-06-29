from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.knowledge_chunk import KnowledgeChunk


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"
from src.services.knowledge.chunk_service import mark_chunks_index_failed
from tests.helpers.chunk_payload import minimal_chunk_orm_kwargs


def _seed_chunk(db_session, kb_id, *, chunk_id: int, embedding_status: str = "indexing"):
    chunk = KnowledgeChunk(
        id=chunk_id,
        kb_id=kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        doc_id=uuid4(),
        primary_node_id=str(uuid4()),
        content_hash=f"hash-{chunk_id}",
        token_count=3,
        embedding_status=embedding_status,
        **minimal_chunk_orm_kwargs(),
    )
    db_session.add(chunk)
    db_session.commit()
    return chunk


def test_mark_chunks_index_failed_updates_only_indexing(db_session, seeded_kb):
    indexing = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=1, embedding_status="indexing")
    ready = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=2, embedding_status="ready")

    result = mark_chunks_index_failed(
        db_session,
        kb_id=seeded_kb.kb_id,
        chunk_ids=[indexing.id, ready.id, 999],
    )

    assert result.updated_ids == [1]
    assert sorted(result.skipped_ids) == [2, 999]
    db_session.refresh(indexing)
    db_session.refresh(ready)
    assert indexing.embedding_status == "failed"
    assert ready.embedding_status == "ready"


def test_mark_chunks_index_failed_respects_kb_isolation(db_session, seeded_kb):
    other_kb_id = uuid4()
    chunk = _seed_chunk(db_session, other_kb_id, chunk_id=10, embedding_status="indexing")

    result = mark_chunks_index_failed(
        db_session,
        kb_id=seeded_kb.kb_id,
        chunk_ids=[chunk.id],
    )

    assert result.updated_ids == []
    assert result.skipped_ids == [10]
    db_session.refresh(chunk)
    assert chunk.embedding_status == "indexing"
