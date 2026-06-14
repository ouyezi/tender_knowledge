from docx import Document

from src.services.docx_content_collector import collect_content


def _build_docx(path, lines):
    doc = Document()
    for style, text in lines:
        doc.add_paragraph(text, style=style)
    doc.save(path)


def test_collect_content_preserves_order_and_skips_empty(tmp_path):
    docx = tmp_path / "collect.docx"
    _build_docx(
        docx,
        [
            ("Normal", "第一章 总则"),
            ("Normal", ""),
            ("Normal", "正文段落"),
            ("Normal", "一、背景"),
        ],
    )
    result = collect_content(docx)
    paragraphs = [b for b in result.blocks if b.block_type == "paragraph"]
    assert [b.text for b in paragraphs] == ["第一章 总则", "正文段落", "一、背景"]
    assert len(paragraphs) == 3
