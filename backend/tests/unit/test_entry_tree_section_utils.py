from src.services.knowledge.entry_tree_section_utils import (
    infer_structure_from_section_numbers,
    parse_section_no,
)


def test_parse_section_no_dotted():
    assert parse_section_no("2.1合同条款偏离表12") == "2.1"
    assert parse_section_no("8.2.1访问控制和身份验证263") == "8.2.1"


def test_parse_section_no_single():
    assert parse_section_no("8信息安全保护措施262") == "8"


def test_parse_section_no_none():
    assert parse_section_no("评分索引表10") is None
    assert parse_section_no("") is None


def test_infer_structure_parent_and_level():
    nodes = [
        {"node_id": "n1", "title": "2服务偏离表12", "level": 3, "parent_id": None, "sort_order": 0},
        {"node_id": "n2", "title": "2.1合同条款偏离表12", "level": 3, "parent_id": None, "sort_order": 1},
        {"node_id": "n3", "title": "2.2技术条款偏离表13", "level": 3, "parent_id": None, "sort_order": 2},
    ]
    patches = infer_structure_from_section_numbers(nodes)
    by_id = {p["node_id"]: p for p in patches}
    assert by_id["n1"]["level"] == 1
    assert by_id["n1"]["parent_id"] is None
    assert by_id["n2"]["level"] == 2
    assert by_id["n2"]["parent_id"] == "n1"
    assert by_id["n3"]["parent_id"] == "n1"
