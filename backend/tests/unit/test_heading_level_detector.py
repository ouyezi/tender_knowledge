import pytest

from src.services.heading_level_detector import detect_heading_level


@pytest.mark.parametrize(
    "text,style,expected_level,expected_pattern",
    [
        ("### 实施方案", None, 3, "markdown"),
        ("第一章 总则", None, 1, "chinese_chapter"),
        ("第一节 概述", None, 2, "chinese_section"),
        ("一、项目背景", None, 2, "chinese_list"),
        ("（一）建设目标", None, 3, "chinese_paren_list"),
        ("1.2.3 技术要求", None, 3, "numeric"),
        ("1 总则", None, 1, "numeric"),
        ("这是普通正文段落", None, None, None),
    ],
)
def test_detect_heading_level_patterns(text, style, expected_level, expected_pattern):
    result = detect_heading_level(text, style)
    if expected_level is None:
        assert result is None
        return
    assert result.level == expected_level
    assert result.pattern == expected_pattern


def test_detect_heading_style_takes_priority_over_markdown():
    result = detect_heading_level("### 标题", "Heading 2")
    assert result is not None
    assert result.pattern == "heading_style"
    assert result.level == 2
    assert result.confidence == "high"


def test_numbered_body_paragraph_on_normal_style_not_heading():
    result = detect_heading_level(
        "1. 根据贵方采购文件要求，我方郑重承诺将按比选文件全部要求履行合同责任和义务。",
        "Normal",
    )
    assert result is None


def test_heading_style_numeric_section_still_detected():
    result = detect_heading_level("1.参选人业绩", "Heading 2")
    assert result is not None
    assert result.pattern == "heading_style"


def test_chinese_patterns_have_medium_confidence():
    result = detect_heading_level("第一章 总则", None)
    assert result is not None
    assert result.confidence == "medium"

