from src.config import settings


def test_blueprint_generate_defaults():
    assert settings.blueprint_generate_model == "qwen-plus"
    assert settings.blueprint_generate_timeout_sec == 60
    assert settings.blueprint_generate_max_tokens == 20480
