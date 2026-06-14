import re

_LEADING_PATTERNS = [
    re.compile(r"^\s*\d+(?:\.\d+)*[\.、\s-]*"),
    re.compile(r"^\s*[（(][一二三四五六七八九十0-9]+[)）][、\s-]*"),
    re.compile(r"^\s*第\s*[0-9一二三四五六七八九十]+\s*[章节篇部]\s*"),
]


def normalize_outline_title(title: str) -> str:
    normalized = (title or "").strip()
    for pattern in _LEADING_PATTERNS:
        normalized = pattern.sub("", normalized, count=1).strip()
    return normalized
