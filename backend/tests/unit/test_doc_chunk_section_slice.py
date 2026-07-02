from src.services.doc_chunk.markdown_blocks import markdown_to_blocks
from src.services.doc_chunk.section_content import section_blocks_for_outline_node
from src.services.doc_chunk.section_slice import slice_section_markdown_from_payload


def test_slice_section_from_payload_uses_anchor_char_start():
    content_md = (
        "承诺人：某公司\n\n"
        "### （四）不违法分包转包承诺书\n\n"
        "错误段落\n\n"
        "##### (6)九阳\n\n"
        "![docx-img-457](images/docx-img-457.png)\n\n"
        "##### (7)美的\n\n"
        "下一节\n"
    )
    n71_start = content_md.index("##### (6)九阳")
    n72_start = content_md.index("##### (7)美的")
    outline_payload = {
        "nodes": [
            {
                "node_id": "n71",
                "title": "(6)九阳",
                "level": 5,
                "parent_id": "n70",
                "sort_order": 71,
                "anchor": {"char_start": n71_start, "char_end": n71_start + 20},
            },
            {
                "node_id": "n72",
                "title": "(7)美的",
                "level": 5,
                "parent_id": "n70",
                "sort_order": 72,
                "anchor": {"char_start": n72_start, "char_end": n72_start + 20},
            },
        ]
    }

    markdown = slice_section_markdown_from_payload(content_md, outline_payload, "n71")
    assert markdown is not None
    assert "(6)九阳" in markdown
    assert "不违法分包转包承诺书" not in markdown
    assert "docx-img-457" in markdown

    blocks = section_blocks_for_outline_node(content_md, outline_payload, "n71")
    assert any("九阳" in str(block.get("text") or "") for block in blocks)
    assert any(block.get("type") == "image" for block in blocks)


def test_markdown_to_blocks_splits_paragraphs_and_images():
    blocks = markdown_to_blocks("标题\n\n段落一\n\n![img](images/docx-img-1.png)")
    assert blocks[0]["type"] == "paragraph"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[2]["type"] == "image"
    assert blocks[2]["image_ref"] == "images/docx-img-1.png"


from uuid import uuid4

from src.services.doc_chunk.section_slice import (
    outline_nodes_from_tree_nodes,
    slice_section_markdown,
)


def test_outline_nodes_from_tree_nodes_and_parent_slice():
    parent_id = uuid4()
    child_id = uuid4()
    nodes = [
        type("N", (), {
            "node_id": parent_id,
            "title": "第一章",
            "level": 1,
            "parent_id": None,
            "sort_order": 1,
        })(),
        type("N", (), {
            "node_id": child_id,
            "title": "1.1 小节",
            "level": 2,
            "parent_id": parent_id,
            "sort_order": 2,
        })(),
    ]
    content_md = "# 第一章\n\n父内容\n\n## 1.1 小节\n\n子内容\n\n## 1.2 其他\n\n忽略"
    outline = outline_nodes_from_tree_nodes(nodes)
    parent_md = slice_section_markdown(content_md, outline, str(parent_id))
    assert parent_md is not None
    assert "父内容" in parent_md
    assert "子内容" in parent_md
    assert "1.2 其他" not in parent_md


def test_slice_section_matches_heading_with_trailing_page_number_in_tree_title():
    content_md = "# 服务偏离表\n\n## 合同条款偏离表\n\n正文\n\n### 2.1合同条款偏离表\n\n表格内容\n"
    outline = [
        type("N", (), {
            "node_id": "n1",
            "title": "2.1合同条款偏离表12",
            "level": 3,
            "parent_id": None,
            "sort_order": 1,
        })(),
    ]
    section = slice_section_markdown(content_md, outline_nodes_from_tree_nodes(outline), "n1")
    assert section is not None
    assert "表格内容" in section


from src.services.doc_chunk.section_slice import slice_section_by_anchor


def _outline_with_anchors(content_md: str) -> dict:
    parent_start = content_md.index("# 第一章")
    child_start = content_md.index("## 1.1")
    sibling_start = content_md.index("## 1.2")
    return {
        "nodes": [
            {
                "node_id": "n1",
                "title": "第一章 总则",
                "level": 1,
                "parent_id": None,
                "sort_order": 0,
                "anchor": {"char_start": parent_start, "char_end": parent_start + 10},
            },
            {
                "node_id": "n2",
                "title": "1.1 范围",
                "level": 2,
                "parent_id": "n1",
                "sort_order": 1,
                "anchor": {"char_start": child_start, "char_end": child_start + 10},
            },
            {
                "node_id": "n3",
                "title": "1.2 其他",
                "level": 2,
                "parent_id": "n1",
                "sort_order": 2,
                "anchor": {"char_start": sibling_start, "char_end": sibling_start + 10},
            },
        ]
    }


def test_slice_section_by_anchor_child_section():
    content_md = "# 第一章 总则\n\n父内容\n\n## 1.1 范围\n\n子内容\n\n## 1.2 其他\n\n忽略\n"
    outline = _outline_with_anchors(content_md)
    md = slice_section_by_anchor(content_md, outline, "n2")
    assert md is not None
    assert "子内容" in md
    assert "父内容" not in md
    assert "忽略" not in md


def test_slice_section_by_anchor_parent_includes_children():
    content_md = "# 第一章 总则\n\n父内容\n\n## 1.1 范围\n\n子内容\n\n## 1.2 其他\n\n忽略\n"
    outline = _outline_with_anchors(content_md)
    md = slice_section_by_anchor(content_md, outline, "n1")
    assert md is not None
    assert "父内容" in md
    assert "子内容" in md
    assert "忽略" in md


def test_slice_section_by_anchor_ignores_db_level_mismatch():
    content_md = "# 第一章 总则\n\n父内容\n\n## 1.1 范围\n\n子内容\n\n## 1.2 其他\n\n忽略\n"
    outline = _outline_with_anchors(content_md)
    outline["nodes"][0]["level"] = 3
    md = slice_section_by_anchor(content_md, outline, "n1")
    assert md is not None
    assert "子内容" in md
