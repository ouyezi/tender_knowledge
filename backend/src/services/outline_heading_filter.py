from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from pathlib import Path
from typing import Any, Literal

from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.heading_level_detector import (
    detect_heading_level,
    is_numbered_body_paragraph,
    looks_like_numbered_body_title,
)
from src.services.outline_text_utils import effective_body_text

logger = logging.getLogger(__name__)
_RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "outline_filter_rules.yaml"
_DATE_LINE_RE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月")
_EMBEDDED_CHAPTER_ONE_RE = re.compile(r"^第一章\s*\S")
_DEFAULT_RULES: dict[str, Any] = {
    "quality": {"l1_ratio_warn": 0.6, "min_nodes_for_l1_warn": 30, "review_ratio_warn": 0.4},
    "filter": {
        "body_list_min_length": 80,
        "date_line_max_length": 40,
        "parent_keywords_body_list": ["参选", "承诺", "声明", "响应函"],
    },
}


@dataclass
class HeadingFilterDecision:
    temp_id: str
    action: Literal["keep", "exclude"]
    reason_code: str
    title: str
    level: int


@dataclass
class FilterStats:
    excluded: int = 0
    kept: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)


@dataclass
class FilterResult:
    kept: list[TocEntry]
    decisions: list[HeadingFilterDecision]
    stats: FilterStats


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.rstrip()
        stripped = line.strip()
        i += 1
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        while len(stack) > 1 and indent < stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().strip("'\"")
        value = value.strip()
        if value == "":
            list_items: list[str] = []
            j = i
            while j < len(lines):
                next_line = lines[j].rstrip()
                next_stripped = next_line.strip()
                if not next_stripped or next_stripped.startswith("#"):
                    j += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip(" "))
                if next_indent <= indent:
                    break
                if next_stripped.startswith("- "):
                    list_items.append(next_stripped[2:].strip().strip("'\""))
                    j += 1
                    continue
                break
            if list_items:
                current[key] = list_items
                i = j
                continue
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent + 2, child))
            continue
        lowered = value.lower()
        if lowered in {"null", "~", "none"}:
            parsed: Any = None
        elif value.startswith(("'", '"')) and value.endswith(("'", '"')):
            parsed = value[1:-1]
        else:
            try:
                parsed = float(value) if "." in value else int(value)
            except ValueError:
                parsed = value
        current[key] = parsed
    return root


def _load_rules() -> dict[str, Any]:
    if not _RULES_PATH.exists():
        logger.warning("outline_filter_rules missing, using defaults path=%s", _RULES_PATH)
        return _DEFAULT_RULES
    try:
        parsed = _parse_minimal_yaml(_RULES_PATH.read_text(encoding="utf-8"))
        return parsed if parsed else _DEFAULT_RULES
    except Exception:
        logger.exception("failed to load outline_filter_rules, using defaults")
        return _DEFAULT_RULES


def _parent_title(entries_by_id: dict[str, TocEntry], parent_temp_id: str | None) -> str:
    if not parent_temp_id:
        return ""
    parent = entries_by_id.get(parent_temp_id)
    return parent.title if parent else ""


def _ancestor_titles(entries_by_id: dict[str, TocEntry], parent_temp_id: str | None) -> list[str]:
    titles: list[str] = []
    current = parent_temp_id
    while current:
        parent = entries_by_id.get(current)
        if parent is None:
            break
        titles.append(parent.title)
        current = parent.parent_temp_id
    return titles


def _classify_entry(
    entry: TocEntry,
    *,
    strategy: ExtractStrategy,
    rules: dict[str, Any],
    entries_by_id: dict[str, TocEntry],
    following_body: str,
) -> HeadingFilterDecision:
    filt = rules.get("filter", {})
    if strategy == ExtractStrategy.toc:
        return HeadingFilterDecision(entry.temp_id, "keep", "toc_native", entry.title, entry.level)

    detection = detect_heading_level(entry.title)
    if (
        detection is not None
        and detection.pattern == "chinese_chapter"
        and entry.level <= 2
        and _EMBEDDED_CHAPTER_ONE_RE.match(entry.title.strip())
    ):
        return HeadingFilterDecision(entry.temp_id, "exclude", "embedded_document", entry.title, entry.level)
    if detection is not None and detection.confidence == "high" and detection.pattern == "heading_style":
        return HeadingFilterDecision(entry.temp_id, "keep", "heading_style_high", entry.title, entry.level)

    max_date_len = int(filt.get("date_line_max_length", 40))
    if len(entry.title) <= max_date_len and _DATE_LINE_RE.search(entry.title):
        return HeadingFilterDecision(entry.temp_id, "exclude", "date_line", entry.title, entry.level)

    parent_title = _parent_title(entries_by_id, entry.parent_temp_id)
    ancestors = _ancestor_titles(entries_by_id, entry.parent_temp_id)
    keywords = filt.get("parent_keywords_body_list") or []
    min_body_len = int(filt.get("body_list_min_length", 80))
    if looks_like_numbered_body_title(entry.title):
        return HeadingFilterDecision(entry.temp_id, "exclude", "body_paragraph", entry.title, entry.level)

    if detection is not None and is_numbered_body_paragraph(entry.title, None, detection):
        return HeadingFilterDecision(entry.temp_id, "exclude", "body_paragraph", entry.title, entry.level)

    if (
        detection is not None
        and detection.pattern == "numeric"
        and entry.level == 1
        and len(entry.title) >= 30
        and not entry.parent_temp_id
    ):
        return HeadingFilterDecision(entry.temp_id, "exclude", "orphan_body_list", entry.title, entry.level)

    if (
        detection is not None
        and detection.pattern == "numeric"
        and entry.level <= 2
        and len(entry.title) >= min_body_len
        and ancestors
    ):
        return HeadingFilterDecision(entry.temp_id, "exclude", "section_context_body", entry.title, entry.level)

    if (
        detection is not None
        and detection.pattern == "numeric"
        and entry.level <= 2
        and len(entry.title) >= min_body_len
        and any(kw in parent_title for kw in keywords)
    ):
        return HeadingFilterDecision(entry.temp_id, "exclude", "body_list_item", entry.title, entry.level)

    if not effective_body_text(following_body) and not effective_body_text(entry.title):
        return HeadingFilterDecision(entry.temp_id, "exclude", "structural_only", entry.title, entry.level)

    return HeadingFilterDecision(entry.temp_id, "keep", "default", entry.title, entry.level)


def filter_outline_entries(
    entries: list[TocEntry],
    *,
    blocks: list | None = None,
    strategy: ExtractStrategy,
    block_text_by_heading_index: dict[int, str] | None = None,
) -> FilterResult:
    _ = blocks
    rules = _load_rules()
    entries_by_id = {e.temp_id: e for e in entries}
    decisions: list[HeadingFilterDecision] = []
    kept: list[TocEntry] = []
    stats = FilterStats()

    for entry in sorted(entries, key=lambda e: e.sort_order):
        following = (block_text_by_heading_index or {}).get(entry.sort_order, "")
        decision = _classify_entry(
            entry,
            strategy=strategy,
            rules=rules,
            entries_by_id=entries_by_id,
            following_body=following,
        )
        decisions.append(decision)
        if decision.action == "keep":
            kept.append(entry)
            stats.kept += 1
        else:
            stats.excluded += 1
            stats.by_reason[decision.reason_code] = stats.by_reason.get(decision.reason_code, 0) + 1

    return FilterResult(kept=kept, decisions=decisions, stats=stats)
