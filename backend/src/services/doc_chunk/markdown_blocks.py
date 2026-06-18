from __future__ import annotations

import re
from typing import Any

_IMAGE_LINE_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    text = markdown.strip()
    if not text:
        return []

    blocks: list[dict[str, Any]] = []
    for part in re.split(r"\n\n+", text):
        chunk = part.strip()
        if not chunk:
            continue
        image_match = _IMAGE_LINE_RE.match(chunk)
        if image_match:
            image_path = image_match.group(1).strip()
            image_ref = _image_ref_from_path(image_path)
            blocks.append({"type": "image", "image_ref": image_ref})
            continue
        blocks.append({"type": "paragraph", "text": chunk})
    return blocks


def _image_ref_from_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized
