from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from src.config import Settings
from src.services.doc_chunk.blocks_v1 import chunk_blocks_to_content
from src.services.doc_chunk.workspace_loader import load_workspace
from src.services.doc_chunk.workspace_manager import (
    cleanup_workspace,
    ensure_workspace,
    workspace_path_for_task,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_workspace_path_for_task():
    kb_id = uuid4()
    import_id = uuid4()
    task_id = uuid4()
    path = workspace_path_for_task(
        storage_root=Path("/data"),
        kb_id=kb_id,
        import_id=import_id,
        parse_task_id=task_id,
    )
    assert path == Path("/data") / "doc_chunk_workspaces" / str(kb_id) / str(import_id) / str(task_id)


def test_ensure_and_cleanup_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("DOC_CHUNK_WORKSPACE_RETENTION_ON_SUCCESS", "false")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "old.txt").write_text("x", encoding="utf-8")
    ensure_workspace(ws, overwrite=True)
    assert not any(ws.iterdir())
    (ws / "manifest.json").write_text("{}", encoding="utf-8")
    cleanup_workspace(ws, on_success=True)
    assert not ws.exists()


def test_chunk_blocks_to_content_maps_image_asset():
    asset_id = uuid4()
    content = chunk_blocks_to_content(
        [
            {"type": "paragraph", "text": "hello"},
            {"type": "image", "image_ref": "images/a.png"},
        ],
        image_ref_map={"images/a.png": asset_id},
    )
    assert str(asset_id) in content
    assert "hello" in content


def test_load_minimal_workspace_fixture():
    loaded = load_workspace(FIXTURE_ROOT)
    assert loaded.manifest["status"] == "success"
    assert len(loaded.outline.get("nodes") or []) == 2
    assert len(loaded.document_tree.get("nodes") or []) == 3
    assert len(loaded.linkage.get("entries") or []) == 2
