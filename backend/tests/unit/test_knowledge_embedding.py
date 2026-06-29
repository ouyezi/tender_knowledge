from __future__ import annotations

from uuid import uuid4

from src.models.chunk_asset import ChunkAsset
from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.embedding_task import (
    embed_knowledge_chunk,
    get_embedding_status,
)
from src.services.knowledge.embedding_client import EmbeddingResult


def _clear_embedding_credentials(monkeypatch):
    monkeypatch.delenv("EMBEDDING_API_BASE", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.setattr("src.config.settings.embedding_api_base", None)
    monkeypatch.setattr("src.config.settings.embedding_api_key", None)
    monkeypatch.setattr("src.config.settings.llm_api_key", None)


def _seed_chunk(db_session, kb_id, *, content: str = "chunk body", summary: str = "chunk summary"):
    chunk = KnowledgeChunk(
        id=1,
        kb_id=kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        title="Test chunk",
        content=content,
        summary=summary,
        knowledge_type="fact",
        doc_id=uuid4(),
        block_type_code="product_solution",
        application_type_code="preferred_reference",
        business_line_codes=["general"],
        primary_node_id=str(uuid4()),
        content_hash="abc123",
        token_count=3,
    )
    db_session.add(chunk)
    db_session.commit()
    return chunk


def _mock_embed(monkeypatch, *, vector: list[float] | None = None):
    def fake_embed_text(_self, text: str) -> EmbeddingResult:
        if vector is None:
            return EmbeddingResult(vector=None, disabled_reason="embedding_request_failed")
        return EmbeddingResult(vector=vector)

    monkeypatch.setattr(
        "src.services.knowledge.embedding_task.EmbeddingClient.embed_text",
        fake_embed_text,
    )
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://embedding.test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")


def test_embed_knowledge_chunk_upserts_chunk_embedding(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    _mock_embed(monkeypatch, vector=[0.1, 0.2, 0.3])

    status = embed_knowledge_chunk(db_session, chunk.id)

    assert status == "ready"
    row = (
        db_session.query(ChunkEmbedding)
        .filter(
            ChunkEmbedding.object_type == "chunk",
            ChunkEmbedding.object_id == chunk.id,
        )
        .one()
    )
    assert row.content_embedding == [0.1, 0.2, 0.3]
    assert row.summary_embedding == [0.1, 0.2, 0.3]


def test_embed_knowledge_chunk_embeds_linked_assets(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    asset = ChunkAsset(
        id=10,
        kb_id=seeded_kb.kb_id,
        doc_id=chunk.doc_id,
        chunk_id=chunk.id,
        asset_type="table",
        raw_markdown="| A | B |",
        llm_summary="table summary",
    )
    db_session.add(asset)
    db_session.commit()
    _mock_embed(monkeypatch, vector=[0.4, 0.5, 0.6])

    status = embed_knowledge_chunk(db_session, chunk.id)

    assert status == "ready"
    asset_row = (
        db_session.query(ChunkEmbedding)
        .filter(
            ChunkEmbedding.object_type == "asset",
            ChunkEmbedding.object_id == asset.id,
        )
        .one()
    )
    assert asset_row.content_embedding == [0.4, 0.5, 0.6]
    assert asset_row.summary_embedding == [0.4, 0.5, 0.6]


def test_embed_knowledge_chunk_skipped_when_not_configured(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    _clear_embedding_credentials(monkeypatch)

    status = embed_knowledge_chunk(db_session, chunk.id)

    assert status == "skipped"
    assert (
        db_session.query(ChunkEmbedding)
        .filter(
            ChunkEmbedding.object_type == "chunk",
            ChunkEmbedding.object_id == chunk.id,
        )
        .count()
        == 0
    )


def test_embed_knowledge_chunk_failed_when_chunk_missing(db_session, monkeypatch):
    _mock_embed(monkeypatch, vector=[0.1])

    status = embed_knowledge_chunk(db_session, 999)

    assert status == "failed"


def test_embed_knowledge_chunk_failed_when_embedding_fails(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    _mock_embed(monkeypatch, vector=None)

    status = embed_knowledge_chunk(db_session, chunk.id)

    assert status == "failed"
    row = (
        db_session.query(ChunkEmbedding)
        .filter(
            ChunkEmbedding.object_type == "chunk",
            ChunkEmbedding.object_id == chunk.id,
        )
        .one()
    )
    assert row.content_embedding is None
    assert row.summary_embedding is None


def test_get_embedding_status_pending(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://embedding.test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")

    assert get_embedding_status(db_session, chunk.id) == "pending"


def test_get_embedding_status_ready(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    chunk.embedding_status = "ready"
    db_session.commit()

    assert get_embedding_status(db_session, chunk.id) == "ready"


def test_get_embedding_status_failed(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    chunk.embedding_status = "failed"
    db_session.commit()

    assert get_embedding_status(db_session, chunk.id) == "failed"


def test_get_embedding_status_skipped(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    _clear_embedding_credentials(monkeypatch)

    assert get_embedding_status(db_session, chunk.id) == "skipped"
