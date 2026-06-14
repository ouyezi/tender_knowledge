from pathlib import Path

from docx import Document

from src.services.docx_document_walker import walk_document

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-actual-bid.docx"


def test_walk_document_returns_heading_and_paragraph_nodes():
    result = walk_document(FIXTURE)
    node_types = {n.node_type for n in result.nodes}
    assert "heading" in node_types
    assert "paragraph" in node_types
    headings = [n for n in result.nodes if n.node_type == "heading"]
    assert all(h.level >= 1 for h in headings)


def _build_chinese_outline_docx(path: Path) -> None:
    doc = Document()
    for text in [
        "第一章 项目概述",
        "本项目旨在建设数字化平台。",
        "一、建设背景",
        "背景说明正文。",
        "### 技术路线",
        "技术细节正文。",
    ]:
        doc.add_paragraph(text, style="Normal")
    doc.save(path)


def test_walk_document_detects_chinese_hierarchy(tmp_path):
    docx = tmp_path / "chinese.docx"
    _build_chinese_outline_docx(docx)
    result = walk_document(docx)
    assert result.used_flat_fallback is False
    headings = [n for n in result.nodes if n.node_type == "heading"]
    assert [h.level for h in headings] == [1, 2, 3]
    paragraphs = [n for n in result.nodes if n.node_type == "paragraph"]
    assert all(p.parent_temp_id is not None for p in paragraphs)
