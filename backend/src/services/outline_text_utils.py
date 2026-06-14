from __future__ import annotations

import re

_IMAGE_PLACEHOLDER_RE = re.compile(r"^\[image\]$", re.IGNORECASE)
_MARKDOWN_IMAGE_RE = re.compile(r"^!\[[^\]]*]\([^)]+\)\s*$")
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")


def effective_body_text(text: str | None) -> str:
    if not text:
        return ""
    stripped = text.strip()
    if not stripped:
        return ""
    if _IMAGE_PLACEHOLDER_RE.match(stripped) or _MARKDOWN_IMAGE_RE.match(stripped):
        return ""
    if _MARKDOWN_HEADING_RE.match(stripped):
        return ""
    return stripped
