from datetime import datetime, timezone

from e2e.kb_setup import build_kb_name


def test_build_kb_name_prefix():
    name = build_kb_name(now=datetime(2026, 6, 14, 10, 30, 0, tzinfo=timezone.utc))
    assert name.startswith("铁建验收-20260614-")
