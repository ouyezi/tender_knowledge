from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from src.services.content_blocks import blocks_v1


def resolve_image_asset_id(image_ref: str, image_ref_map: dict[str, UUID]) -> UUID | None:
    ref = image_ref.strip().replace("\\", "/")
    if not ref:
        return None
    if ref in image_ref_map:
        return image_ref_map[ref]

    basename = Path(ref).name
    candidates = [ref, f"images/{basename}", basename]
    if "/" not in ref:
        for ext in (".png", ".jpeg", ".jpg"):
            candidates.append(f"images/{ref}{ext}")
            candidates.append(f"{ref}{ext}")

    for key in candidates:
        asset_id = image_ref_map.get(key)
        if asset_id is not None:
            return asset_id

    for key, asset_id in image_ref_map.items():
        if key == basename or key.endswith(f"/{basename}"):
            return asset_id
    return None


def chunk_blocks_to_content(
    blocks: list[dict[str, Any]],
    *,
    image_ref_map: dict[str, UUID] | None = None,
) -> str:
    mapped: list[dict[str, Any]] = []
    image_ref_map = image_ref_map or {}

    for block in blocks:
        block_type = block.get("type")
        if block_type in {"paragraph", "table"}:
            text = str(block.get("text") or "").strip()
            if text:
                mapped.append({"type": block_type, "text": text})
            continue
        if block_type == "image":
            image_ref = str(block.get("image_ref") or "").strip()
            asset_id = resolve_image_asset_id(image_ref, image_ref_map)
            if asset_id is not None:
                item: dict[str, Any] = {"type": "image", "asset_id": str(asset_id)}
                if image_ref:
                    item["image_ref"] = image_ref
                mapped.append(item)
            elif image_ref:
                mapped.append({"type": "image", "fallback": "[image]", "image_ref": image_ref})
            else:
                mapped.append({"type": "image", "fallback": "[image]"})

    return blocks_v1(mapped)
