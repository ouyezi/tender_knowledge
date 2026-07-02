from src.config import settings


def test_entry_tree_refine_defaults():
    assert settings.entry_tree_refine_model == "qwen-plus"
    assert settings.entry_tree_refine_max_tokens == 10000
    assert settings.entry_tree_refine_timeout_sec == 120
    assert settings.entry_tree_refine_batch_size == 400
