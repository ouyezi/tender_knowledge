from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import UUID

from src.config import Settings


def content_md_path(*, document_id: UUID, storage_root: Path | None = None) -> Path:
    root = storage_root or Path(Settings().storage_root)
    return root / "documents" / str(document_id) / "content.md"


def image_ref_map_path(*, document_id: UUID, storage_root: Path | None = None) -> Path:
    root = storage_root or Path(Settings().storage_root)
    return root / "documents" / str(document_id) / "image_ref_map.json"


def persist_content_md(
    *,
    document_id: UUID,
    source_path: Path,
    storage_root: Path | None = None,
) -> Path | None:
    if not source_path.is_file():
        return None
    dest = content_md_path(document_id=document_id, storage_root=storage_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest)
    return dest


def persist_image_ref_map(
    *,
    document_id: UUID,
    image_ref_map: dict[str, UUID],
    storage_root: Path | None = None,
) -> Path | None:
    if not image_ref_map:
        return None
    dest = image_ref_map_path(document_id=document_id, storage_root=storage_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: str(value) for key, value in image_ref_map.items()}
    dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return dest


def load_content_md(*, document_id: UUID, storage_root: Path | None = None) -> str | None:
    path = content_md_path(document_id=document_id, storage_root=storage_root)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load_image_ref_map(*, document_id: UUID, storage_root: Path | None = None) -> dict[str, UUID]:
    path = image_ref_map_path(document_id=document_id, storage_root=storage_root)
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
