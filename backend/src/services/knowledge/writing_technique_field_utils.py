from __future__ import annotations

TITLE_MAX = 30
APPLICABLE_SCENE_MAX = 100
WRITING_SUMMARY_MAX = 200
WRITING_STRATEGY_MAX = 200

VALID_USAGE_MODES = frozenset({"DIRECT", "REFERENCE", "EXTRACT"})


def truncate_technique_field(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len]


def clamp_confidence(value: object) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def coerce_usage_mode(value: object) -> str:
    mode = str(value or "").strip().upper()
    if mode in VALID_USAGE_MODES:
        return mode
    return "REFERENCE"
