from src.config import settings
from src.services.chunk_classification_service import classify_chunk
from src.services.knowledge_chunk import KnowledgeChunk


def test_classify_chunk_without_llm_uses_rule(db_session, seeded_kb, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    chunk = KnowledgeChunk(
        chunk_ref="n1",
        chunk_type="chapter",
        title="售后服务方案",
        content_preview="我们提供支持",
    )
    result, degraded = classify_chunk(db_session, kb_id=seeded_kb.kb_id, chunk=chunk)
    assert result.suggestion_source == "rule"
    assert degraded is True


def test_classify_chunk_with_mock_llm(db_session, seeded_kb, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    def fake_chat(**kwargs):
        from src.services.llm_client import LLMResponse

        return LLMResponse(
            content='{"chapter_taxonomy_hint":"售后服务方案","knowledge_type":"scheme","confidence":0.9}',
            model="test",
            provider="qwen",
        )

    monkeypatch.setattr("src.services.chunk_classification_service.chat_completion", fake_chat)
    chunk = KnowledgeChunk(
        chunk_ref="n1",
        chunk_type="candidate",
        title="方案段",
        content_preview="详细方案内容",
    )
    result, degraded = classify_chunk(db_session, kb_id=seeded_kb.kb_id, chunk=chunk)
    assert result.suggestion_source in ("llm", "hybrid")
    assert degraded is False
