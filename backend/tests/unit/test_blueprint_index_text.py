from src.services.knowledge.blueprint_index_text import (
    build_highlights,
    build_search_text,
    compute_content_hash,
    exact_match_bonus,
    keyword_score,
)


SAMPLE_DETAIL = {
    "name": "政务云技术方案",
    "description": "面向政府的云架构蓝图",
    "product_tags": ["政务云"],
    "industry_tags": ["政府"],
    "scenario_tags": ["IaaS"],
    "applicable_project_type": ["信息化建设"],
    "suggested_structure_md": "## 技术架构",
    "nodes": [
        {
            "node_title": "总体架构",
            "content_description": "描述云平台分层",
            "tender_response_hint": "响应架构评分点",
            "children": [],
        }
    ],
}


def test_build_search_text_includes_name_and_nodes():
    text = build_search_text(SAMPLE_DETAIL)
    assert "政务云技术方案" in text
    assert "总体架构" in text
    assert "政务云" in text


def test_compute_content_hash_stable():
    h1 = compute_content_hash("abc")
    h2 = compute_content_hash("abc")
    assert h1 == h2
    assert h1 != compute_content_hash("xyz")


def test_keyword_score_matches_name():
    score = keyword_score(
        keyword="政务云",
        name="政务云技术方案",
        description="",
        search_text="政务云技术方案",
    )
    assert score == 1.0


def test_keyword_score_weights_name_higher_than_body_only():
    tokens = "餐补 产品 功能 介绍"
    name_score = keyword_score(
        keyword=tokens,
        name="餐补产品功能介绍",
        description="",
        search_text="",
    )
    body_score = keyword_score(
        keyword=tokens,
        name="无关标题",
        description="餐补产品功能介绍全文",
        search_text="",
    )
    assert name_score == 1.0
    assert body_score == 0.25
    assert name_score > body_score


def test_exact_match_bonus_for_title_query():
    bonus = exact_match_bonus(
        semantic_query="餐补产品功能介绍",
        keyword="餐补 产品 功能 介绍",
        name="餐补产品功能介绍",
    )
    assert bonus == 0.35


def test_build_highlights_wraps_em():
    highlights = build_highlights(
        keyword="政务云 技术",
        name="政务云技术方案",
        description="",
        search_text="政务云技术方案描述",
    )
    assert highlights
    assert "<em>" in highlights[0]["snippet"]
