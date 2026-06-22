from __future__ import annotations

import hashlib
import re
from typing import Any


def _join_tags(tags: list[Any] | None) -> str:
    return " ".join(str(item).strip() for item in (tags or []) if str(item).strip())


def _flatten_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    for node in nodes or []:
        title = str(node.get("node_title") or "").strip()
        cd = str(node.get("content_description") or "").strip()
        tr = str(node.get("tender_response_hint") or "").strip()
        if title:
            parts.append(title)
        if cd:
            parts.append(cd)
        if tr:
            parts.append(tr)
        parts.extend(_flatten_nodes(node.get("children") or []))
    return parts


def build_search_text(detail: dict[str, Any]) -> str:
    sections = [
        str(detail.get("name") or "").strip(),
        str(detail.get("description") or "").strip(),
        _join_tags(detail.get("product_tags")),
        _join_tags(detail.get("industry_tags")),
        _join_tags(detail.get("scenario_tags")),
        _join_tags(detail.get("applicable_project_type")),
        str(detail.get("suggested_structure_md") or "").strip(),
        *_flatten_nodes(detail.get("nodes") or []),
    ]
    return "\n".join(part for part in sections if part)


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _keyword_tokens(keyword: str) -> list[str]:
    return [token for token in re.split(r"\s+", keyword.strip()) if token]


def keyword_score(*, keyword: str, name: str, description: str | None, search_text: str) -> float:
    tokens = _keyword_tokens(keyword)
    if not tokens:
        return 0.0
    fields = [name or "", description or "", search_text or ""]
    matched = 0
    for token in tokens:
        token_lower = token.lower()
        if any(token_lower in field.lower() for field in fields):
            matched += 1
    return matched / len(tokens)


def _highlight_text(text: str, keyword: str, *, field: str, max_len: int = 200) -> dict[str, str] | None:
    tokens = _keyword_tokens(keyword)
    if not text or not tokens:
        return None
    snippet = text[:max_len]
    for token in tokens:
        pattern = re.compile(re.escape(token), re.IGNORECASE)
        snippet = pattern.sub(lambda m: f"<em>{m.group(0)}</em>", snippet)
    if "<em>" not in snippet:
        return None
    return {"field": field, "snippet": snippet}


def build_highlights(
    *,
    keyword: str,
    name: str,
    description: str | None,
    search_text: str,
) -> list[dict[str, str]]:
    highlights: list[dict[str, str]] = []
    for field, value in (
        ("name", name),
        ("description", description or ""),
        ("search_text", search_text),
    ):
        item = _highlight_text(value, keyword, field=field)
        if item:
            highlights.append(item)
    return highlights
