from src.config import settings


def test_writing_technique_generate_defaults():
    assert settings.writing_technique_generate_model == "qwen-plus"
    assert settings.writing_technique_generate_timeout_sec == 30
