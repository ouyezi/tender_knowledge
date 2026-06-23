from __future__ import annotations

import hashlib
import re


def build_index_content_hash(*, title: str, summary: str | None, content: str) -> str:
    text = f"{title.strip()}\n{(summary or '').strip()}\n{content.strip()}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _keyword_tokens(keyword: str) -> list[str]:
    return [token for token in re.split(r"\s+", keyword.strip()) if token]


def _token_hit_ratio(tokens: list[str], field: str) -> float:
    if not tokens or not field:
        return 0.0
    field_lower = field.lower()
    matched = sum(1 for token in tokens if token.lower() in field_lower)
    return matched / len(tokens)


def chunk_keyword_score(
    *,
    keyword: str,
    title: str,
    summary: str | None,
    content: str,
    title_weight: float = 3.0,
    body_weight: float = 1.0,
) -> float:
    tokens = _keyword_tokens(keyword)
    if not tokens:
        return 0.0
    title_ratio = _token_hit_ratio(tokens, title or "")
    body_field = f"{summary or ''}\n{content or ''}"
    body_ratio = _token_hit_ratio(tokens, body_field)
    if title_ratio >= 1.0:
        return 1.0
    weight_sum = max(title_weight + body_weight, 1e-9)
    return min(1.0, (title_weight * title_ratio + body_weight * body_ratio) / weight_sum)


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def chunk_exact_match_bonus(
    *,
    semantic_query: str,
    keyword: str,
    title: str,
    boost: float = 0.35,
) -> float:
    norm_title = _normalize_match_text(title)
    if not norm_title or boost <= 0:
        return 0.0
    for candidate in (
        _normalize_match_text(semantic_query),
        _normalize_match_text(keyword.replace(" ", "")),
    ):
        if candidate and candidate == norm_title:
            return boost
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


def build_chunk_highlights(
    *,
    keyword: str,
    title: str,
    summary: str | None,
    content: str,
) -> list[dict[str, str]]:
    highlights: list[dict[str, str]] = []
    for field, value in (("title", title), ("summary", summary or ""), ("content", content)):
        item = _highlight_text(value, keyword, field=field)
        if item:
            highlights.append(item)
    return highlights
