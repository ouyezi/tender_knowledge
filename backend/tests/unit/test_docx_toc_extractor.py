from pathlib import Path

from docx import Document

from src.services.docx_document_walker import DocumentWalkResult
from src.services.docx_toc_extractor import ExtractStrategy, extract_toc_entries

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-actual-bid.docx"


def test_extract_toc_fallback_to_heading_when_no_builtin_toc():
    result = extract_toc_entries(FIXTURE)
    assert len(result.entries) >= 1
    assert result.strategy in {
        ExtractStrategy.toc,
        ExtractStrategy.heading_heuristic,
        ExtractStrategy.content_heuristic,
        ExtractStrategy.flat_fallback,
    }
    assert result.entries[0].title.strip() != ""


def test_extract_toc_uses_content_heuristic_for_chinese_outline(tmp_path):
    doc = Document()
    for text in ["第一章 总则", "一、背景"]:
        doc.add_paragraph(text, style="Normal")
    path = tmp_path / "ch.docx"
    doc.save(path)
    result = extract_toc_entries(path)
    assert result.strategy == ExtractStrategy.content_heuristic
    assert result.entries[0].level == 1
    assert result.entries[1].parent_temp_id == result.entries[0].temp_id


def test_extract_toc_entries_degrades_when_snapshot_incomplete():
    broken = DocumentWalkResult(nodes=[], used_flat_fallback=True, needs_manual_review=True)
    result = extract_toc_entries(FIXTURE, infer_snapshot=broken)
    assert result.entries
    assert result.strategy.value in {
        "toc",
        "heading_heuristic",
        "content_heuristic",
        "flat_fallback",
    }
