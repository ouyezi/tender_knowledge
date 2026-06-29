from __future__ import annotations

import re
from datetime import date, datetime

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize_certificate_number(value: str | None) -> str | None:
    if not value:
        return None
    seen: set[str] = set()
    parts: list[str] = []
    for raw in str(value).split(","):
        item = raw.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        parts.append(item)
    return ",".join(parts) if parts else None


def normalize_certificate_date(value: str | None) -> str | None:
    if not value:
        return None
    parts: list[str] = []
    for raw in str(value).split(","):
        item = raw.strip()
        if not item:
            continue
        if not _ISO_DATE_RE.match(item):
            continue
        parts.append(item)
    return ",".join(parts) if parts else None


def _parse_iso_date(value: str) -> date | None:
    if not _ISO_DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def earliest_expire_date(values: list[str]) -> date | None:
    dates = [_parse_iso_date(item) for item in values]
    parsed = [item for item in dates if item is not None]
    return min(parsed) if parsed else None


def earliest_expire_date_from_csv(value: str | None) -> date | None:
    if not value:
        return None
    return earliest_expire_date([part.strip() for part in value.split(",") if part.strip()])


def parse_expire_date_value(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if "," in text:
        return earliest_expire_date_from_csv(text)
    return _parse_iso_date(text)
