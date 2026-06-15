from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.config import Settings
from src.models.document import Document
from src.models.document_media_asset import DocumentMediaAsset
from src.services.doc_chunk.types import ImportContext


def import_media_assets(
    db: Session,
    *,
    ctx: ImportContext,
    document: Document,
    kb_id: UUID,
) -> dict[str, UUID]:
    images_manifest = None
    manifest_path = ctx.workspace_path / "images" / "manifest.json"
    if manifest_path.exists():
        import json

        images_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    image_ref_map: dict[str, UUID] = {}
    if not images_manifest:
        ctx.image_ref_map = image_ref_map
        return image_ref_map

    storage_root = Path(Settings().storage_root)
    images_dir = ctx.workspace_path / "images"

    for entry in images_manifest.get("images") or []:
        image_ref = str(entry.get("image_ref") or "").strip()
        if not image_ref:
            continue
        source_path = images_dir / Path(image_ref).name
        if not source_path.exists():
            source_path = ctx.workspace_path / image_ref
        if not source_path.exists():
            continue

        content_type = str(entry.get("content_type") or "application/octet-stream")
        ext = mimetypes.guess_extension(content_type) or Path(entry.get("file_name") or source_path.name).suffix or ".bin"
        asset_id = uuid4()
        rel_path = Path(str(kb_id)) / "media" / str(document.document_id) / f"{asset_id}{ext}"
        dest = storage_root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest)

        db.add(
            DocumentMediaAsset(
                asset_id=asset_id,
                kb_id=kb_id,
                document_id=document.document_id,
                storage_path=str(rel_path).replace("\\", "/"),
                mime_type=content_type,
                source_block_index=entry.get("source_block_index"),
            )
        )
        image_ref_map[image_ref] = asset_id

    db.flush()
    ctx.image_ref_map = image_ref_map
    return image_ref_map
