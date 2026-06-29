from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class QualificationRecord:
    name: str
    number: str
    issue_date: str
    expire_text: str


def _parse_iso_date(value: str) -> date | None:
    if not _ISO_DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_iso_segment(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    return text if _parse_iso_date(text) else ""


def _split_record(raw: str) -> QualificationRecord | None:
    parts = [part.strip() for part in raw.split("|")]
    while len(parts) < 4:
        parts.append("")
    name, number, issue_date, expire_text = parts[:4]
    if not any((name, number, issue_date, expire_text)):
        return None
    return QualificationRecord(
        name=name,
        number=number,
        issue_date=_normalize_iso_segment(issue_date),
        expire_text=expire_text.strip(),
    )


def format_qualification_record(
    *,
    name: str,
    number: str,
    issue_date: str,
    expire_text: str,
) -> str:
    return "|".join(
        (
            name.strip(),
            number.strip(),
            _normalize_iso_segment(issue_date),
            expire_text.strip(),
        )
    )


def parse_qualification_records(value: str | None) -> list[QualificationRecord]:
    if not value:
        return []
    records: list[QualificationRecord] = []
    for raw in str(value).split(";"):
        record = _split_record(raw)
        if record is not None:
            records.append(record)
    return records


def normalize_qualification_info(value: str | None) -> str | None:
    if not value:
        return None
    seen: set[str] = set()
    normalized: list[str] = []
    for record in parse_qualification_records(value):
        formatted = format_qualification_record(
            name=record.name,
            number=record.number,
            issue_date=record.issue_date,
            expire_text=record.expire_text,
        )
        if formatted in seen:
            continue
        seen.add(formatted)
        normalized.append(formatted)
    if not normalized:
        return None
    result = ";".join(normalized)
    return result[:2048] if len(result) > 2048 else result


def earliest_expire_date_from_qualification_info(value: str | None) -> date | None:
    dates: list[date] = []
    for record in parse_qualification_records(value):
        parsed = _parse_iso_date(record.expire_text)
        if parsed is not None:
            dates.append(parsed)
    return min(dates) if dates else None


def parse_expire_date_value(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if "," in text:
        dates = [_parse_iso_date(part.strip()) for part in text.split(",")]
        parsed = [item for item in dates if item is not None]
        return min(parsed) if parsed else None
    return _parse_iso_date(text)
