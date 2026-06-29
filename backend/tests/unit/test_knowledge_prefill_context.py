from src.services.knowledge.knowledge_prefill_context import (
    format_catalog_breadcrumb,
    summarize_assets,
)
from src.services.knowledge.knowledge_prefill_prompt import build_system_prompt


def test_format_catalog_breadcrumb():
    path = [
        {"title": "第一章", "level": 1},
        {"title": "1.1 资质证明", "level": 2},
    ]
    assert format_catalog_breadcrumb(path) == "第一章 > 1.1 资质证明"


def test_summarize_assets():
    summary = summarize_assets(
        [{"asset_type": "table"}, {"asset_type": "image"}, {"asset_type": "image"}]
    )
    assert summary["total"] == 3
    assert summary["has_table"] is True
    assert summary["has_image"] is True


def test_build_system_prompt_includes_taxonomy_codes():
    prompt = build_system_prompt()
    assert "block_type_code" in prompt
    assert "ip_patent" in prompt
    assert "meal_subsidy" in prompt
    assert "fixed_reference" in prompt
