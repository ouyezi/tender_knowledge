import json
import os
from pathlib import Path

import pytest

from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.outline_heading_filter import filter_outline_entries

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "dingxin-golden-titles.json"
BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "dingxin-baseline-stats.json"


def _normalize_title(title: str) -> str:
    return "".join(title.split())


def _entry(title: str, *, temp_id: str, sort_order: int, level: int = 1, parent: str | None = None) -> TocEntry:
    return TocEntry(
        temp_id=temp_id,
        parent_temp_id=parent,
        title=title,
        level=level,
        sort_order=sort_order,
    )


def _synthetic_noisy_outline(golden_titles: list[str]) -> list[TocEntry]:
    """Simulate dingxin-like noise: genuine chapters + date lines + body list items."""
    entries: list[TocEntry] = []
    order = 0
    for idx, title in enumerate(golden_titles[:10]):
        entries.append(_entry(title, temp_id=f"g{idx}", sort_order=order))
        order += 1
    parent_id = "g1"
    for idx in range(15):
        entries.append(
            _entry(
                f"1. 根据贵方采购文件要求，我方郑重承诺将按比选文件全部要求履行合同责任和义务，"
                f"并保证所提供的服务完全符合比选文件规定的全部技术标准和商务条款要求（条目{idx}）。",
                temp_id=f"n{idx}",
                sort_order=order,
                parent=parent_id,
            )
        )
        order += 1
    for idx in range(10):
        entries.append(_entry(f"2026 年 {idx + 1} 月 19 日", temp_id=f"d{idx}", sort_order=order))
        order += 1
    for idx, title in enumerate(golden_titles[10:20]):
        entries.append(_entry(title, temp_id=f"g2{idx}", sort_order=order))
        order += 1
    return entries


@pytest.mark.skipif(not GOLDEN.exists(), reason="golden titles fixture not committed yet")
def test_dingxin_golden_titles_fixture_has_minimum_entries():
    titles = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(titles) >= 20


@pytest.mark.skipif(not GOLDEN.exists() or not BASELINE.exists(), reason="fixtures missing")
def test_dingxin_golden_titles_retention_offline():
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    entries = _synthetic_noisy_outline(golden)
    assert len(entries) >= baseline["unfiltered_node_count"]

    filtered = filter_outline_entries(
        entries,
        blocks=[],
        strategy=ExtractStrategy.content_heuristic,
    )
    kept_titles = {_normalize_title(e.title) for e in filtered.kept}
    input_golden = golden[:20]
    matched = sum(1 for t in input_golden if _normalize_title(t) in kept_titles)
    retention = matched / len(input_golden)
    assert retention >= baseline["min_golden_retention_ratio"], f"retention={retention:.2%}"


@pytest.mark.skipif(not GOLDEN.exists() or not BASELINE.exists(), reason="fixtures missing")
def test_dingxin_node_reduction_offline():
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    entries = _synthetic_noisy_outline(golden)
    unfiltered = len(entries)

    filtered = filter_outline_entries(
        entries,
        blocks=[],
        strategy=ExtractStrategy.content_heuristic,
    )
    kept = len(filtered.kept)
    reduction = 1 - (kept / unfiltered) if unfiltered else 0
    assert reduction >= baseline["min_reduction_ratio"], f"reduction={reduction:.2%}, kept={kept}"


@pytest.mark.skipif(not os.getenv("DINGXIN_DOCM"), reason="set DINGXIN_DOCM=/path/to/鼎信餐补标书.docm")
def test_dingxin_node_reduction_and_golden_retention_local_docm():
    pytest.skip("optional local E2E — run manually with DINGXIN_DOCM set")
