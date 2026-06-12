from pathlib import Path

from docx import Document

from src.services.docx_outline_parser import parse_outline


def _build_docx(path: Path, lines: list[tuple[str, str]]) -> None:
    doc = Document()
    for style_name, text in lines:
        doc.add_paragraph(text, style=style_name)
    doc.save(path)


def test_parse_outline_prefers_heading_styles(tmp_path):
    docx_path = tmp_path / "heading.docx"
    _build_docx(
        docx_path,
        [
            ("Heading 1", "1 项目概述"),
            ("Normal", "这是正文"),
            ("Heading 2", "1.1 项目背景"),
            ("Heading 1", "2 技术方案"),
        ],
    )

    nodes = parse_outline(docx_path)
    assert [node.title for node in nodes] == ["1 项目概述", "1.1 项目背景", "2 技术方案"]
    assert [node.level for node in nodes] == [1, 2, 1]
    assert nodes[1].parent_temp_id == nodes[0].temp_id
    assert all(node.needs_manual_review is False for node in nodes)


def test_parse_outline_falls_back_to_numbered_prefix(tmp_path):
    docx_path = tmp_path / "numbered.docx"
    _build_docx(
        docx_path,
        [
            ("Normal", "1 总则"),
            ("Normal", "1.1 适用范围"),
            ("Normal", "2 技术要求"),
        ],
    )

    nodes = parse_outline(docx_path)
    assert [node.level for node in nodes] == [1, 2, 1]
    assert nodes[1].parent_temp_id == nodes[0].temp_id
    assert all(node.needs_manual_review is False for node in nodes)


def test_parse_outline_marks_manual_review_when_no_headings(sample_docx_path):
    nodes = parse_outline(sample_docx_path)
    assert len(nodes) >= 1
    assert all(node.needs_manual_review is True for node in nodes)
