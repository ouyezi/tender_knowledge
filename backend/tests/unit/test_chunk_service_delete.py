from __future__ import annotations

from uuid import uuid4

from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.chunk_service import ChunkNotFoundError, delete_knowledge_chunk


def _seed_chunk(db_session, kb_id, *, chunk_id: int = 1, knowledge_code: str | None = None):
    doc_id = uuid4()
    code = knowledge_code or str(uuid4())
    chunk = KnowledgeChunk(
        id=chunk_id,
        kb_id=kb_id,
        knowledge_code=code,
        version="1.0",
        is_latest=True,
        title="测试知识",
        content="测试内容",
        knowledge_type="section",
        content_type="text",
        doc_id=doc_id,
        block_type_code="product_solution",
        application_type_code="preferred_reference",
        business_line_codes=["general"],
        content_hash="hash-1",
        primary_node_id=str(uuid4()),
        token_count=2,
    )
    db_session.add(chunk)
    db_session.flush()
    return chunk


def test_delete_knowledge_chunk_removes_chunk_and_embedding(db_session, seeded_kb):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    db_session.add(
        ChunkEmbedding(
            object_type="chunk",
            object_id=chunk.id,
            content_hash="hash-1",
        )
    )
    db_session.commit()

    delete_knowledge_chunk(db_session, kb_id=seeded_kb.kb_id, chunk_id=chunk.id)
    db_session.commit()

    assert (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.kb_id == seeded_kb.kb_id, KnowledgeChunk.id == chunk.id)
        .count()
        == 0
    )
    assert (
        db_session.query(ChunkEmbedding)
        .filter(
            ChunkEmbedding.object_type == "chunk",
            ChunkEmbedding.object_id == chunk.id,
        )
        .count()
        == 0
    )


def test_delete_knowledge_chunk_removes_all_versions(db_session, seeded_kb):
    code = str(uuid4())
    first = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=1, knowledge_code=code)
    second = KnowledgeChunk(
        id=2,
        kb_id=seeded_kb.kb_id,
        knowledge_code=code,
        version="1.1",
        previous_version_id=first.id,
        is_latest=True,
        title="测试知识 v2",
        content="测试内容 v2",
        knowledge_type="section",
        content_type="text",
        doc_id=first.doc_id,
        block_type_code="product_solution",
        application_type_code="preferred_reference",
        business_line_codes=["general"],
        content_hash="hash-2",
        primary_node_id=first.primary_node_id,
        token_count=3,
    )
    db_session.add(second)
    db_session.commit()

    delete_knowledge_chunk(db_session, kb_id=seeded_kb.kb_id, chunk_id=second.id)
    db_session.commit()

    assert db_session.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_code == code).count() == 0


def test_delete_knowledge_chunk_not_found(db_session, seeded_kb):
    try:
        delete_knowledge_chunk(db_session, kb_id=seeded_kb.kb_id, chunk_id=9999)
        assert False, "expected ChunkNotFoundError"
    except ChunkNotFoundError:
        pass
