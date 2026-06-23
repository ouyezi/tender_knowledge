from __future__ import annotations

from uuid import uuid4

from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.chunk_index_task import index_knowledge_chunk
from src.services.knowledge.embedding_client import EmbeddingResult


def _seed_chunk(db_session, kb_id):
    chunk = KnowledgeChunk(
        id=1,
        kb_id=kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        title="Test chunk",
        content="chunk body",
        summary="chunk summary",
        knowledge_type="fact",
        doc_id=uuid4(),
        source_type="bid",
        category="technical",
        primary_node_id=str(uuid4()),
        content_hash="abc123",
        token_count=3,
        embedding_status="pending",
    )
    db_session.add(chunk)
    db_session.commit()
    return chunk


def test_index_knowledge_chunk_ready(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)

    monkeypatch.setattr(
        "src.services.knowledge.chunk_index_task.rewrite_chunk_summary",
        lambda **_: {"summary": "新摘要", "date_confidence": "low"},
    )

    def fake_embed_text(_self, text: str) -> EmbeddingResult:
        return EmbeddingResult(vector=[0.1, 0.2, 0.3])

    monkeypatch.setattr(
        "src.services.knowledge.chunk_index_task.EmbeddingClient.embed_text",
        fake_embed_text,
    )
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://embedding.test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")

    status = index_knowledge_chunk(db_session, chunk.id)

    assert status == "ready"
    db_session.refresh(chunk)
    assert chunk.embedding_status == "ready"
    assert chunk.summary == "新摘要"
    row = (
        db_session.query(ChunkEmbedding)
        .filter(
            ChunkEmbedding.object_type == "chunk",
            ChunkEmbedding.object_id == chunk.id,
        )
        .one()
    )
    assert row.title_embedding == [0.1, 0.2, 0.3]
    assert row.content_embedding == [0.1, 0.2, 0.3]
