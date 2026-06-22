from __future__ import annotations

CONTENT_SUMMARY_MAX = 800
CONTENT_DESCRIPTION_MAX = 200
TENDER_RESPONSE_HINT_MAX = 300
SUGGESTED_STRUCTURE_MD_MAX = 1500


def truncate_blueprint_field(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len]
