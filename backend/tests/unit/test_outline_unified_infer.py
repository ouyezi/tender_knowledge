from pathlib import Path
from unittest.mock import patch

from src.services.docx_document_walker import walk_document
from src.services.docx_toc_extractor import extract_toc_entries

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-chinese-outline.docx"


def test_extract_toc_entries_reuses_infer_snapshot_without_second_collect():
    if not FIXTURE.exists():
        import pytest

        pytest.skip("fixture missing")
    walked = walk_document(FIXTURE)
    assert walked.collected is not None
    assert walked.infer_result is not None

    with patch("src.services.docx_toc_extractor.collect_content") as mock_collect:
        result = extract_toc_entries(FIXTURE, infer_snapshot=walked)
        mock_collect.assert_not_called()
    assert len(result.entries) > 0
