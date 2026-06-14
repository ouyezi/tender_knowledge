from __future__ import annotations

from pathlib import Path
from typing import Any

from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.outline_heading_filter import FilterStats, HeadingFilterDecision, _load_rules

_RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "outline_filter_rules.yaml"


def summarize_outline_quality(
    entries: list[TocEntry],
    *,
    strategy: ExtractStrategy,
    filter_stats: FilterStats,
    raw_count: int,
    needs_manual_review_count: int = 0,
    embedded_regions: list | None = None,
    embedded_heading_count: int = 0,
) -> dict[str, Any]:
    node_count = len(entries)
    l1_count = sum(1 for e in entries if e.level == 1)
    max_depth = max((e.level for e in entries), default=0)
    l1_ratio = (l1_count / node_count) if node_count else 0.0
    review_ratio = (needs_manual_review_count / node_count) if node_count else 0.0

    rules = _load_rules().get("quality", {})
    warnings: list[str] = []
    if node_count == 0:
        warnings.append("empty_outline")
    if strategy == ExtractStrategy.flat_fallback:
        warnings.append("flat_fallback")
    if (
        node_count > int(rules.get("min_nodes_for_l1_warn", 30))
        and l1_ratio > float(rules.get("l1_ratio_warn", 0.6))
    ):
        warnings.append("high_l1_ratio")
    if review_ratio > float(rules.get("review_ratio_warn", 0.4)):
        warnings.append("high_review_ratio")
    if embedded_regions:
        warnings.append("embedded_document_detected")

    embedded_sample = [
        {
            "trigger_title": r.trigger_title[:120],
            "resume_title": (r.resume_title or "")[:120],
            "skipped_heading_count": r.skipped_heading_count,
        }
        for r in (embedded_regions or [])[:5]
    ]

    return {
        "node_count": node_count,
        "raw_candidate_count": raw_count,
        "max_depth": max_depth or 1,
        "l1_count": l1_count,
        "l1_ratio": round(l1_ratio, 4),
        "needs_manual_review_count": needs_manual_review_count,
        "review_ratio": round(review_ratio, 4),
        "extract_strategy": strategy.value,
        "warnings": warnings,
        "filter_stats": {
            "excluded": filter_stats.excluded,
            "kept": filter_stats.kept,
            "by_reason": dict(filter_stats.by_reason),
        },
        "embedded_heading_count": embedded_heading_count,
        "embedded_regions_sample": embedded_sample,
    }


def sample_excluded_decisions(decisions: list[HeadingFilterDecision], limit: int = 20) -> list[dict[str, Any]]:
    excluded = [d for d in decisions if d.action == "exclude"]
    return [
        {
            "title": d.title[:200],
            "reason_code": d.reason_code,
            "level": d.level,
        }
        for d in excluded[:limit]
    ]
