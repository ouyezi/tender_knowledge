from __future__ import annotations

import re


_VARIABLE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def detect_variables(text: str | None) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _VARIABLE_RE.finditer(text):
        key = match.group(1)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered
