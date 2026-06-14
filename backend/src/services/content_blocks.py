from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

MAX_BLOCK_TEXT_CHARS = 32_000
EMPTY_EXCERPT = "（仅标题）"


@dataclass(frozen=True)
class ParsedContent:
    format: str
    blocks: list[dict[str, Any]]
    plain_text: str | None = None


def blocks_v1(blocks: list[dict[str, Any]]) -> str:
    safe_blocks: list[dict[str, Any]] = []
    for block in blocks:
        item = dict(block)
        text = item.get("text")
        if isinstance(text, str) and len(text) > MAX_BLOCK_TEXT_CHARS:
            item["text"] = text[:MAX_BLOCK_TEXT_CHARS]
        safe_blocks.append(item)
    return json.dumps({"format": "blocks_v1", "blocks": safe_blocks}, ensure_ascii=False)


def parse_content(raw: str | None) -> ParsedContent:
    if not raw:
        return ParsedContent(format="plain", blocks=[], plain_text="")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ParsedContent(format="plain", blocks=[], plain_text=raw)
    if isinstance(payload, dict) and payload.get("format") == "blocks_v1":
        blocks = payload.get("blocks") or []
        if not isinstance(blocks, list):
            blocks = []
        return ParsedContent(format="blocks_v1", blocks=blocks)
    return ParsedContent(format="plain", blocks=[], plain_text=raw)


def content_excerpt(raw: str | None, *, max_len: int = 120) -> str:
    doc = parse_content(raw)
    if doc.format == "plain":
        text = (doc.plain_text or "").strip()
        return text[:max_len] if text else EMPTY_EXCERPT
    for block in doc.blocks:
        if block.get("type") in {"paragraph", "table"}:
            text = str(block.get("text") or "").strip()
            if text:
                return text[:max_len]
        if block.get("type") == "image" and block.get("asset_id"):
            return "[图片]"
    return EMPTY_EXCERPT
