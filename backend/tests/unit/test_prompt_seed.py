from src.services.generation.prompt_seed import GENERATION_PROMPT_VERSION


def test_generation_prompt_version_is_v1():
    assert GENERATION_PROMPT_VERSION == "generation-v1.0.0"
