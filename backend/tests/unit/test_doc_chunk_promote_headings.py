from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.services.doc_chunk.pipeline_runner import run_doc_chunk_pipeline


def test_run_doc_chunk_pipeline_passes_promote_headings(tmp_path: Path) -> None:
    docx = tmp_path / "sample.docx"
    docx.write_bytes(b"PK")
    workspace = tmp_path / "ws"

    with patch("src.services.doc_chunk.pipeline_runner.run_pipeline") as run_pipeline:
        run_doc_chunk_pipeline(docx, workspace)
        _, kwargs = run_pipeline.call_args
        assert kwargs["promote_headings"] == "auto"
        assert kwargs["skip_refine"] is True
