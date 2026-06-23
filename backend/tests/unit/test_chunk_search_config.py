from src.config import settings


def test_knowledge_chunk_retrieval_config_defaults():
    assert settings.knowledge_vision_model == "qwen-vl-max"
    assert settings.knowledge_vision_timeout_sec == 60
    assert settings.knowledge_index_summary_model == "qwen3-max"
    assert settings.chunk_search_parse_model == "qwen3.6-flash"
    assert settings.chunk_search_title_keyword_weight == 3.0
    assert settings.chunk_search_vector_min_similarity == 0.10
