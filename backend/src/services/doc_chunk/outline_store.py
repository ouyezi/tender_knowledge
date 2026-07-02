from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import UUID

from src.config import Settings


def outline_path(*, document_id: UUID, storage_root: Path | None = None) -> Path:
    root = storage_root or Path(Settings().storage_root)
    return root / "documents" / str(document_id) / "outline.json"


def outline_node_map_path(*, document_id: UUID, storage_root: Path | None = None) -> Path:
    root = storage_root or Path(Settings().storage_root)
    return root / "documents" / str(document_id) / "outline_node_map.json"


def persist_outline(
    *,
    document_id: UUID,
    outline_payload: dict[str, Any],
    storage_root: Path | None = None,
) -> Path | None:
    if not outline_payload:
        return None
    dest = outline_path(document_id=document_id, storage_root=storage_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(outline_payload, ensure_ascii=False), encoding="utf-8")
    return dest


def persist_outline_from_source(
    *,
    document_id: UUID,
    source_path: Path,
    storage_root: Path | None = None,
) -> Path | None:
    if not source_path.is_file():
        return None
    dest = outline_path(document_id=document_id, storage_root=storage_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest)
    return dest


def persist_outline_node_map(
    *,
    document_id: UUID,
    outline_node_to_tree_id: dict[str, UUID],
    storage_root: Path | None = None,
) -> Path | None:
    if not outline_node_to_tree_id:
        return None
    dest = outline_node_map_path(document_id=document_id, storage_root=storage_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: str(value) for key, value in outline_node_to_tree_id.items()}
    dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return dest


def load_outline(*, document_id: UUID, storage_root: Path | None = None) -> dict[str, Any] | None:
    path = outline_path(document_id=document_id, storage_root=storage_root)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def load_outline_node_map(
    *, document_id: UUID, storage_root: Path | None = None
) -> dict[str, UUID]:
    path = outline_node_map_path(document_id=document_id, storage_root=storage_root)
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    result: dict[str, UUID] = {}
    for key, value in payload.items():
        try:
            result[str(key)] = UUID(str(value))
        except ValueError:
            continue
    return result


def resolve_outline_node_id(
    *,
    document_id: UUID,
    tree_node_id: UUID | str,
    storage_root: Path | None = None,
) -> str | None:
    node_map = load_outline_node_map(document_id=document_id, storage_root=storage_root)
    target = str(tree_node_id)
    for outline_node_id, mapped_tree_id in node_map.items():
        if str(mapped_tree_id) == target:
            return outline_node_id
    return None
