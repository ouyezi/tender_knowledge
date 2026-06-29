from __future__ import annotations

from datetime import date


def normalize_business_line_codes(codes: list[str] | None) -> list[str]:
    if not codes:
        return ["general"]
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in codes:
        code = str(raw).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized or ["general"]


def compute_is_expired(expire_date: date | None, *, today: date | None = None) -> bool:
    if expire_date is None:
        return False
    ref = today or date.today()
    return expire_date < ref
