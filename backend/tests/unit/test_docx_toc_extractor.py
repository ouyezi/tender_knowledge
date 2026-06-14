from pathlib import Path

from src.services.docx_toc_extractor import ExtractStrategy, extract_toc_entries

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-actual-bid.docx"


def test_extract_toc_fallback_to_heading_when_no_builtin_toc():
    result = extract_toc_entries(FIXTURE)
    assert len(result.entries) >= 1
    assert result.strategy in {
        ExtractStrategy.toc,
        ExtractStrategy.heading_heuristic,
        ExtractStrategy.flat_fallback,
    }
    assert result.entries[0].title.strip() != ""
