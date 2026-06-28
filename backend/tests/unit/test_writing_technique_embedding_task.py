from src.services.knowledge.writing_technique_index_text import build_search_text


def test_build_search_text_joins_fields():
    detail = {
        "title": "标题",
        "applicable_scene": "场景",
        "writing_summary": "简介",
        "tags": ["标签A"],
        "writing_strategy": "策略",
        "must_include": "要点",
    }
    text = build_search_text(detail)
    assert "标题" in text
    assert "标签A" in text
    assert "策略" in text
