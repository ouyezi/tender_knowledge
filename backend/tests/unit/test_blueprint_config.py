from src.config import settings


def test_blueprint_generate_defaults():
    assert settings.blueprint_generate_model == "qwen3.6-flash"
    assert settings.blueprint_generate_timeout_sec == 60
    assert settings.blueprint_generate_max_tokens == 65536
