import pytest

from src.services.outline_text_utils import effective_body_text


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", ""),
        ("   ", ""),
        ("# 标题", ""),
        ("一、报价表格式", "一、报价表格式"),
        ("1. 根据贵方采购文件要求我方承诺提供服务。", "1. 根据贵方采购文件要求我方承诺提供服务。"),
        ("![img](x.png)", ""),
        ("[image]", ""),
    ],
)
def test_effective_body_text(raw, expected):
    assert effective_body_text(raw) == expected
