from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.outline_heading_filter import FilterStats
from src.services.outline_quality_service import summarize_outline_quality


def _entry(title: str, level: int, sort_order: int = 0):
    return TocEntry(
        temp_id=f"n{sort_order + 1}",
        parent_temp_id=None,
        title=title,
        level=level,
        sort_order=sort_order,
    )


def test_summarize_emits_high_l1_warning():
    entries = [_entry(f"章节{i}", 1, sort_order=i) for i in range(40)]
    stats = FilterStats(excluded=10, kept=40, by_reason={"body_list_item": 10})
    summary = summarize_outline_quality(
        entries,
        strategy=ExtractStrategy.content_heuristic,
        filter_stats=stats,
        raw_count=50,
    )
    assert summary["node_count"] == 40
    assert summary["l1_ratio"] == 1.0
    assert "high_l1_ratio" in summary["warnings"]


def test_flat_fallback_always_warns():
    summary = summarize_outline_quality(
        [_entry("A", 1)],
        strategy=ExtractStrategy.flat_fallback,
        filter_stats=FilterStats(kept=1),
        raw_count=1,
    )
    assert "flat_fallback" in summary["warnings"]
