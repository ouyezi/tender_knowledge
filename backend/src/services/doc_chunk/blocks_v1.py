from __future__ import annotations

from typing import Any
from uuid import UUID

from src.services.content_blocks import blocks_v1


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
            asset_id = image_ref_map.get(image_ref)
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
