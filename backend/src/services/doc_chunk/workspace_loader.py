from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.services.doc_chunk.types import DocChunkImportError

_REQUIRED_FILES = (
    "manifest.json",
    "outline.json",
    "document_tree.json",
    "linkage.json",
    "chunks/index.json",
)


@dataclass
class LoadedWorkspace:
    root: Path
    manifest: dict[str, Any]
    outline: dict[str, Any]
    document_tree: dict[str, Any]
    linkage: dict[str, Any]
    chunks_index: dict[str, Any]
    images_manifest: dict[str, Any] | None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DocChunkImportError(f"Missing workspace file: {path}", code="DOC_CHUNK_WORKSPACE_INVALID")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise DocChunkImportError(
            f"Unsupported schema in {path.name}",
            code="DOC_CHUNK_WORKSPACE_INVALID",
        )
    return payload


def load_workspace(workspace: Path) -> LoadedWorkspace:
    root = Path(workspace)
    for name in _REQUIRED_FILES:
        if not (root / name).exists():
            raise DocChunkImportError(f"Missing {name}", code="DOC_CHUNK_WORKSPACE_INVALID")

    manifest = _load_json(root / "manifest.json")
    if manifest.get("status") not in {"success", "partial_success"}:
        raise DocChunkImportError(
            f"Workspace manifest status: {manifest.get('status')}",
            code="DOC_CHUNK_WORKSPACE_INVALID",
        )

    images_path = root / "images" / "manifest.json"
    images_manifest = _load_json(images_path) if images_path.exists() else None

    return LoadedWorkspace(
        root=root,
        manifest=manifest,
        outline=_load_json(root / "outline.json"),
        document_tree=_load_json(root / "document_tree.json"),
        linkage=_load_json(root / "linkage.json"),
        chunks_index=_load_json(root / "chunks/index.json"),
        images_manifest=images_manifest,
    )


def load_chunk_file(workspace: Path, relative_path: str) -> dict[str, Any]:
    path = workspace / relative_path
    if not path.exists():
        raise DocChunkImportError(f"Missing chunk file: {relative_path}", code="DOC_CHUNK_WORKSPACE_INVALID")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise DocChunkImportError(f"Unsupported chunk schema: {relative_path}", code="DOC_CHUNK_WORKSPACE_INVALID")
    return payload
