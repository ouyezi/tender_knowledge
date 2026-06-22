import json
from unittest.mock import MagicMock
from uuid import uuid4

from src.services.knowledge.blueprint_outline_suggest_service import (
    OutlineSuggestFailedError,
    OutlineSuggestValidationError,
    compact_blueprint_detail,
    parse_and_validate_llm_response,
    suggest_outline,
    validate_suggest_node,
    validate_suggest_nodes,
)
from src.services.knowledge.blueprint_service import BlueprintNotFoundError

SAMPLE_DETAIL = {
    "name": "供应链蓝图",
    "description": "模块概要",
    "scenario_tags": ["物流"],
    "product_tags": ["WMS"],
    "industry_tags": ["制造"],
    "suggested_structure_md": "结构说明",
    "nodes": [
        {
            "node_title": "总体设计",
            "importance_level": "required",
            "content_description": "写总体思路",
            "tender_response_hint": "响应评分",
            "children": [],
        }
    ],
}

MOCK_SUGGEST_JSON = json.dumps(
    {
        "outline_title": "政务云建议目录",
        "summary": "突出安全与实施",
        "nodes": [
            {
                "title": "技术方案",
                "content_suggestion": "写技术内容",
                "importance": "required",
                "split_reason": "按评分点拆分",
                "no_split_reason": None,
                "children": [
                    {
                        "title": "总体架构",
                        "content_suggestion": "写架构",
                        "importance": "required",
                        "split_reason": None,
                        "no_split_reason": "不宜再拆",
                        "children": [],
                    }
                ],
            }
        ],
    },
    ensure_ascii=False,
)


def test_compact_blueprint_detail_uses_short_keys():
    compact = compact_blueprint_detail(SAMPLE_DETAIL)
    assert compact["name"] == "供应链蓝图"
    assert compact["nodes"][0]["t"] == "总体设计"
    assert compact["nodes"][0]["imp"] == "required"
    assert compact["nodes"][0]["cd"] == "写总体思路"
    assert "node_title" not in compact["nodes"][0]


def test_validate_suggest_node_leaf_requires_no_split_reason():
    node = {
        "title": "总体设计",
        "content_suggestion": "写思路",
        "importance": "required",
        "split_reason": None,
        "no_split_reason": "单章即可覆盖",
        "children": [],
    }
    assert validate_suggest_node(node, depth=1)["title"] == "总体设计"


def test_validate_suggest_node_parent_requires_split_reason():
    node = {
        "title": "技术方案",
        "content_suggestion": "技术内容",
        "importance": "required",
        "split_reason": "按评分点拆分",
        "no_split_reason": None,
        "children": [
            {
                "title": "架构",
                "content_suggestion": "架构说明",
                "importance": "required",
                "split_reason": None,
                "no_split_reason": "不宜再拆",
                "children": [],
            }
        ],
    }
    result = validate_suggest_node(node, depth=1)
    assert len(result["children"]) == 1


def test_validate_suggest_node_rejects_missing_reason():
    node = {
        "title": "技术方案",
        "content_suggestion": "技术内容",
        "importance": "required",
        "split_reason": None,
        "no_split_reason": None,
        "children": [],
    }
    try:
        validate_suggest_node(node, depth=1)
        assert False, "expected OutlineSuggestValidationError"
    except OutlineSuggestValidationError:
        pass


def test_validate_suggest_node_rejects_depth_over_limit():
    deep = {
        "title": "L1",
        "content_suggestion": "c",
        "importance": "required",
        "split_reason": "r",
        "no_split_reason": None,
        "children": [
            {
                "title": "L2",
                "content_suggestion": "c",
                "importance": "required",
                "split_reason": "r",
                "no_split_reason": None,
                "children": [
                    {
                        "title": "L3",
                        "content_suggestion": "c",
                        "importance": "required",
                        "split_reason": "r",
                        "no_split_reason": None,
                        "children": [
                            {
                                "title": "L4",
                                "content_suggestion": "c",
                                "importance": "required",
                                "split_reason": "r",
                                "no_split_reason": None,
                                "children": [
                                    {
                                        "title": "L5",
                                        "content_suggestion": "c",
                                        "importance": "required",
                                        "split_reason": None,
                                        "no_split_reason": "too deep",
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    try:
        validate_suggest_nodes([deep])
        assert False, "expected OutlineSuggestValidationError"
    except OutlineSuggestValidationError:
        pass


def test_parse_and_validate_llm_response_ok():
    result = parse_and_validate_llm_response(MOCK_SUGGEST_JSON)
    assert result["outline_title"] == "政务云建议目录"
    assert result["nodes"][0]["children"][0]["no_split_reason"] == "不宜再拆"


def test_parse_and_validate_llm_response_invalid_json():
    try:
        parse_and_validate_llm_response("not-json")
        assert False
    except OutlineSuggestFailedError:
        pass


def test_suggest_outline_happy_path(monkeypatch):
    db = MagicMock()
    kb_id = uuid4()
    blueprint_id = uuid4()

    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service.get_blueprint_detail",
        lambda _db, *, kb_id, blueprint_id: SAMPLE_DETAIL | {"blueprint_id": str(blueprint_id)},
    )
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service._chat_with_timeout",
        lambda **_: MOCK_SUGGEST_JSON,
    )

    result = suggest_outline(
        db,
        kb_id=kb_id,
        blueprint_ids=[blueprint_id],
        requirement_description="政务云项目，突出安全合规",
    )
    assert result["outline_title"] == "政务云建议目录"


def test_suggest_outline_blueprint_not_found(monkeypatch):
    db = MagicMock()
    kb_id = uuid4()
    blueprint_id = uuid4()

    def _raise(*_args, **_kwargs):
        raise BlueprintNotFoundError

    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service.get_blueprint_detail",
        _raise,
    )

    try:
        suggest_outline(
            db,
            kb_id=kb_id,
            blueprint_ids=[blueprint_id],
            requirement_description="需求",
        )
        assert False
    except BlueprintNotFoundError:
        pass
