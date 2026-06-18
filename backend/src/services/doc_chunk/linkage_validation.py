from __future__ import annotations

import re
from typing import Any

_NUM_PREFIX_RE = re.compile(
    r"^[一二三四五六七八九十百零]+[、.．]|^\d+(?:\.\d+)*[、.．\s]+"
)


def normalize_title(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = _NUM_PREFIX_RE.sub("", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[（）()【】\[\]《》<>「」\"'“”‘’:：,，.。;；!！?？\-—_·•]", "", text)
    return text


def titles_compatible(heading_title: str | None, chunk_title: str | None) -> bool:
    left = normalize_title(heading_title)
    right = normalize_title(chunk_title)
    if not left or not right:
        return True
    return left == right or left in right or right in left


def chunk_matches_outline_entry(
    *,
    outline_node_id: str | None,
    chunk_payload: dict[str, Any],
) -> bool:
    if not outline_node_id:
        return True
    original_ids = [str(item) for item in (chunk_payload.get("original_node_ids") or [])]
    if not original_ids:
        return True
    return outline_node_id in original_ids
