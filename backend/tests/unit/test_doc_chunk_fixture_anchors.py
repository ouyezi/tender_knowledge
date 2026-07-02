from __future__ import annotations

import json
from pathlib import Path

from src.services.doc_chunk.section_slice import slice_section_by_anchor

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def _load_fixture_outline() -> dict:
    return json.loads((FIXTURE_ROOT / "outline.json").read_text(encoding="utf-8"))


def test_fixture_outline_nodes_have_anchor_char_start():
    outline = _load_fixture_outline()
    nodes = outline.get("nodes") or []
    assert nodes, "fixture outline must have nodes"
    for node in nodes:
        anchor = node.get("anchor") or {}
        assert anchor.get("char_start") is not None, f"{node['node_id']} missing char_start"


def test_fixture_slice_child_section_has_body():
    content_md = (FIXTURE_ROOT / "content.md").read_text(encoding="utf-8")
    outline = _load_fixture_outline()
    child_id = outline["nodes"][1]["node_id"]
    section_md = slice_section_by_anchor(content_md, outline, child_id)
    assert section_md is not None
    assert "二级章节正文" in section_md
    assert "这是正文段落" not in section_md
