from uuid import uuid4

from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.chunk_search_service import search_knowledge_chunks


def _seed_ready_chunk(db_session, kb_id, *, title: str, summary: str, content: str, vector):
    chunk = KnowledgeChunk(
        id=1,
        kb_id=kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        title=title,
        content=content,
        summary=summary,
        knowledge_type="fact",
        doc_id=uuid4(),
        source_type="bid",
        category="technical",
        primary_node_id=str(uuid4()),
        content_hash="abc123",
        token_count=3,
        embedding_status="ready",
    )
    db_session.add(chunk)
    db_session.flush()
    db_session.add(
        ChunkEmbedding(
            object_type="chunk",
            object_id=chunk.id,
            title_embedding=vector,
            summary_embedding=vector,
            content_embedding=vector,
            content_hash="hash",
        )
    )
    db_session.commit()
    return chunk


def test_search_knowledge_chunks_only_ready(db_session, seeded_kb):
    _seed_ready_chunk(
        db_session,
        seeded_kb.kb_id,
        title="ISO9001证书",
        summary="质量管理体系",
        content="正文",
        vector=[1.0, 0.0, 0.0],
    )
    pending = KnowledgeChunk(
        id=2,
        kb_id=seeded_kb.kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        title="pending",
        content="x",
        summary="y",
        knowledge_type="fact",
        doc_id=uuid4(),
        source_type="bid",
        category="technical",
        primary_node_id=str(uuid4()),
        content_hash="def",
        token_count=1,
        embedding_status="pending",
    )
    db_session.add(pending)
    db_session.commit()

    result = search_knowledge_chunks(
        db_session,
        kb_id=seeded_kb.kb_id,
        semantic_query="ISO9001",
        keyword="ISO9001",
        vector_weight=0.6,
        keyword_weight=0.4,
        title_vector_weight=0.25,
        summary_vector_weight=0.35,
        content_vector_weight=0.4,
        top_k=10,
        query_vector=[1.0, 0.0, 0.0],
    )
    assert result["total"] == 1
    assert result["items"][0]["title"] == "ISO9001证书"
