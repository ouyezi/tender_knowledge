from src.services.docx_content_collector import RawBlock
from src.services.docx_hierarchy_inferrer import infer_hierarchy


def _blocks(*lines: str) -> list[RawBlock]:
    return [
        RawBlock(index=i, block_type="paragraph", text=t, style_name="Normal", has_image=False)
        for i, t in enumerate(lines)
    ]


def test_infer_hierarchy_builds_parent_stack():
    blocks = _blocks("第一章 总则", "正文", "一、背景", "（一）目标", "1.1 细节")
    result = infer_hierarchy(blocks)
    assert result.used_flat_fallback is False
    levels = [h.level for h in result.headings]
    assert levels == [1, 2, 3, 2]
    assert result.headings[1].parent_block_index == 0
    assert result.headings[2].parent_block_index == 2
    assert result.headings[3].parent_block_index == 0


def test_infer_hierarchy_empty_headings_triggers_flat_fallback():
    blocks = _blocks("普通正文一段", "普通正文二段")
    result = infer_hierarchy(blocks)
    assert result.used_flat_fallback is True
    assert result.headings == []
