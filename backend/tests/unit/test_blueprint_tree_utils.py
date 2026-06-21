import pytest

from src.services.knowledge.blueprint_tree_utils import (
    assign_node_codes,
    flatten_tree,
    map_llm_flags_to_importance,
    nest_tree,
)


def test_assign_node_codes_nested():
    nodes = [
        {
            "node_title": "A",
            "node_level": 1,
            "children": [
                {"node_title": "A1", "node_level": 2, "children": []},
            ],
        },
    ]
    assign_node_codes(nodes)
    assert nodes[0]["node_code"] == "1"
    assert nodes[0]["children"][0]["node_code"] == "1.1"


def test_flatten_and_nest_roundtrip():
    nested = [{"node_title": "Root", "node_level": 1, "node_order": 0, "children": []}]
    flat = flatten_tree(nested)
    assert len(flat) == 1
    assert flat[0]["node_title"] == "Root"
    back = nest_tree(flat)
    assert back[0]["node_title"] == "Root"


@pytest.mark.parametrize(
    ("required_flag", "recommended_flag", "expected"),
    [
        (True, False, "required"),
        (False, True, "recommended"),
        (False, False, "optional"),
    ],
)
def test_map_llm_flags_to_importance(required_flag, recommended_flag, expected):
    assert map_llm_flags_to_importance(required_flag, recommended_flag) == expected
