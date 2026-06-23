from src.config import settings
from src.services.knowledge.embedding_client import EmbeddingClient, embedding_client_from_settings


def test_embedding_client_falls_back_to_llm_qwen_config(monkeypatch):
    monkeypatch.delenv("EMBEDDING_API_BASE", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.setattr(settings, "embedding_api_base", None)
    monkeypatch.setattr(settings, "embedding_api_key", None)
    monkeypatch.setattr(settings, "llm_provider", "qwen")
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    monkeypatch.setattr(settings, "llm_base_url", None)

    client = embedding_client_from_settings()

    assert client.is_configured
    assert client.api_base == settings.resolved_llm_base_url
    assert client.api_key == "sk-test"
    assert client.model == settings.embedding_model
    assert client.dimensions == settings.embedding_dimensions


def test_embedding_payload_uses_dimensions_only_for_v3_v4():
    assert EmbeddingClient._supports_dimensions("text-embedding-v4")
    assert EmbeddingClient._supports_dimensions("text-embedding-v3")
    assert not EmbeddingClient._supports_dimensions("text-embedding-v2")


def test_embedding_client_prefers_explicit_embedding_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://custom.embed/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")

    client = embedding_client_from_settings(model="custom-model")

    assert client.api_base == "https://custom.embed/v1"
    assert client.api_key == "embed-key"
    assert client.model == "custom-model"
