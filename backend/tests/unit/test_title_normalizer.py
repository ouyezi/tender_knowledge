from src.services.retrieval.title_normalizer import normalize_outline_title


def test_normalize_outline_title_strips_outline_numbers():
    assert normalize_outline_title("1.2 技术方案") == "技术方案"
    assert normalize_outline_title("（一）实施计划") == "实施计划"
    assert normalize_outline_title("第3章 项目组织") == "项目组织"


def test_normalize_outline_title_keeps_plain_title():
    assert normalize_outline_title("技术服务保障") == "技术服务保障"
