from pathlib import Path

import pytest

from src.services.doc_chunk.types import DocChunkImportError
from src.services.doc_chunk.workspace_loader import load_workspace

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_load_workspace_validates_required_files(tmp_path):
    with pytest.raises(DocChunkImportError):
        load_workspace(tmp_path)


def test_load_workspace_rejects_bad_schema(tmp_path):
    (tmp_path / "manifest.json").write_text('{"schema_version":"2.0","status":"success"}', encoding="utf-8")
    for name in ("outline.json", "document_tree.json", "linkage.json"):
        (tmp_path / name).write_text('{"schema_version":"1.0"}', encoding="utf-8")
    (tmp_path / "chunks").mkdir()
    (tmp_path / "chunks" / "index.json").write_text('{"schema_version":"1.0","chunks":[]}', encoding="utf-8")
    with pytest.raises(DocChunkImportError):
        load_workspace(tmp_path)


def test_load_minimal_fixture():
    loaded = load_workspace(FIXTURE_ROOT)
    assert loaded.chunks_index["chunks"][0]["chunk_id"] == "chunk-0001"
