from __future__ import annotations

import re

_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_NON_SPACE_RE = re.compile(r"\S+")


def count_tokens(text: str) -> int:
    """Approximate Qwen-compatible token count without loading a tokenizer."""
    normalized = (text or "").strip()
    if not normalized:
        return 0

    cjk_chars = len(_CJK_CHAR_RE.findall(normalized))
    remaining = _CJK_CHAR_RE.sub(" ", normalized)
    other_tokens = len(_NON_SPACE_RE.findall(remaining))
    return cjk_chars + other_tokens
