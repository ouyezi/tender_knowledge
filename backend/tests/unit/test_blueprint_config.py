from src.config import settings


def test_blueprint_generate_defaults():
    assert settings.blueprint_generate_model == "qwen3.6-flash"
    assert settings.blueprint_generate_timeout_sec == 120
    assert settings.blueprint_generate_max_tokens == 16384


def test_blueprint_suggest_defaults():
    assert settings.blueprint_suggest_model == settings.blueprint_generate_model
    assert settings.blueprint_suggest_timeout_sec == 120
    assert settings.blueprint_suggest_max_tokens == 8192
    assert settings.blueprint_suggest_max_blueprints == 5
    assert settings.blueprint_suggest_requirement_max == 2000
