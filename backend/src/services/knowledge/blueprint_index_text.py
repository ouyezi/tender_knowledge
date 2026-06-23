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


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def _token_hit_ratio(tokens: list[str], field: str) -> float:
    if not tokens or not field:
        return 0.0
    field_lower = field.lower()
    matched = sum(1 for token in tokens if token.lower() in field_lower)
    return matched / len(tokens)


def keyword_score(
    *,
    keyword: str,
    name: str,
    description: str | None,
    search_text: str,
    name_weight: float = 3.0,
    body_weight: float = 1.0,
) -> float:
    tokens = _keyword_tokens(keyword)
    if not tokens:
        return 0.0
    name_ratio = _token_hit_ratio(tokens, name or "")
    body_field = f"{description or ''}\n{search_text or ''}"
    body_ratio = _token_hit_ratio(tokens, body_field)
    if name_ratio >= 1.0:
        return 1.0
    weight_sum = max(name_weight + body_weight, 1e-9)
    return min(1.0, (name_weight * name_ratio + body_weight * body_ratio) / weight_sum)


def exact_match_bonus(
    *,
    semantic_query: str,
    keyword: str,
    name: str,
    boost: float = 0.35,
) -> float:
    norm_name = _normalize_match_text(name)
    if not norm_name or boost <= 0:
        return 0.0
    candidates = {
        _normalize_match_text(semantic_query),
        _normalize_match_text(keyword.replace(" ", "")),
    }
    for candidate in candidates:
        if not candidate:
            continue
        if candidate == norm_name:
            return boost
        if len(candidate) >= 4 and candidate in norm_name and norm_name in candidate:
            return boost * 0.8
    return 0.0


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
