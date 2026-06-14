from __future__ import annotations


def sanitize_pg_text(value: str | None) -> str | None:
    """Strip NUL bytes; PostgreSQL TEXT columns reject \\x00."""
    if not value:
        return None
    cleaned = value.replace("\x00", "")
    return cleaned or None
