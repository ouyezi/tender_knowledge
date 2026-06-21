from __future__ import annotations


def count_tokens(text: str) -> int:
    # NOTE: production should prefer a Qwen-compatible tokenizer when available.
    return len((text or "").split())
