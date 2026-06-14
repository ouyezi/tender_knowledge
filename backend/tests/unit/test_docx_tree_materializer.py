from src.services.docx_content_collector import RawBlock
from src.services.docx_hierarchy_inferrer import InferredHeading, InferResult
from src.services.docx_tree_materializer import MaterializedWalkResult, materialize_walk_result


def test_materialize_assigns_content_to_section():
    blocks = [
        RawBlock(0, "paragraph", "第一章 总则", "Normal", False),
        RawBlock(1, "paragraph", "正文内容", "Normal", False),
        RawBlock(2, "table", "列A | 列B", None, False),
    ]
    inferred = InferResult(
        headings=[
            InferredHeading(0, "第一章 总则", 1, None, "chinese_chapter", "medium"),
        ],
        used_flat_fallback=False,
        patterns_used=["chinese_chapter"],
        medium_confidence_count=1,
    )
    result = materialize_walk_result(blocks, inferred)
    headings = [n for n in result.nodes if n.node_type == "heading"]
    paragraphs = [n for n in result.nodes if n.node_type == "paragraph"]
    tables = [n for n in result.nodes if n.node_type == "table"]
    assert len(headings) == 1
    assert headings[0].level == 1
    assert paragraphs[0].parent_temp_id == headings[0].temp_id
    assert tables[0].section_temp_id == headings[0].temp_id
    assert result.needs_manual_review is True
    assert result.used_flat_fallback is False


def test_materialize_flat_fallback_marks_all_review():
    blocks = [RawBlock(0, "paragraph", "只有正文", "Normal", False)]
    inferred = InferResult(headings=[], used_flat_fallback=True, patterns_used=[], medium_confidence_count=0)
    result = materialize_walk_result(blocks, inferred)
    assert result.used_flat_fallback is True
    assert all(n.needs_manual_review for n in result.nodes)
