from __future__ import annotations

import hashlib
from typing import Any


def _join_tags(tags: list[Any] | None) -> str:
    return " ".join(str(item).strip() for item in (tags or []) if str(item).strip())


def build_search_text(detail: dict[str, Any]) -> str:
    sections = [
        str(detail.get("title") or "").strip(),
        str(detail.get("applicable_scene") or "").strip(),
        str(detail.get("writing_summary") or "").strip(),
        _join_tags(detail.get("tags")),
        str(detail.get("writing_strategy") or "").strip(),
        str(detail.get("must_include") or "").strip(),
    ]
    return "\n".join(part for part in sections if part)


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
