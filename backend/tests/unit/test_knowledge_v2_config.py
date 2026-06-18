from src.config import settings


def test_knowledge_prefill_defaults():
    assert settings.knowledge_prefill_model == "qwen3-max"
    assert settings.knowledge_prefill_timeout_sec == 10
