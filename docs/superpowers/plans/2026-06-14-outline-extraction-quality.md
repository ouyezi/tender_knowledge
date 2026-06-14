# 标书目录提取质量增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 过滤 Bid Outline 伪标题噪声、输出目录质量摘要、统一 walk/extract 推断快照，使鼎信类标书默认目录节点减少 ≥30% 且真章节保留 ≥95%。

**Architecture:** 物化 OutlineNode 后由 `outline_heading_filter` 排除噪声；`outline_quality_service` 计算摘要写入 `document_parse_suggestions.payload`；`extract_toc_entries` 复用 `walk_document` 的 `CollectResult + InferResult`；前端确认向导方案 A（只读过滤列表，无恢复按钮）。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PyYAML, pytest · React 18, Ant Design 5, TypeScript

**Design doc:** `docs/superpowers/specs/2026-06-14-outline-extraction-quality-design.md`  
**Spec:** `specs/005-outline-extraction-quality/spec.md`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/src/config/outline_filter_rules.yaml` | 过滤阈值、父章节关键词 |
| `backend/src/services/outline_text_utils.py` | `effective_body_text` |
| `backend/src/services/outline_heading_filter.py` | 伪标题规则过滤 |
| `backend/src/services/outline_quality_service.py` | 质量摘要 + warnings |
| `backend/src/services/docx_document_walker.py` | `DocumentWalkResult.collected` |
| `backend/src/services/docx_toc_extractor.py` | `infer_snapshot` 参数，避免二次 infer |
| `backend/src/services/actual_bid_parse_runner.py` | 过滤接线、suggestion payload |
| `backend/src/api/routes/actual_bid_parse.py` | `outline_quality`、`file_name`、`filtered_*` |
| `backend/src/api/routes/bid_outlines.py` | 列表项 `outline_quality` |
| `backend/tests/fixtures/dingxin-golden-titles.json` | 真章节基准 ≥20 条 |
| `backend/tests/fixtures/sample-noisy-outline.docx` | CI 噪声过滤夹具 |
| `backend/tests/unit/test_outline_text_utils.py` | 正文工具单测 |
| `backend/tests/unit/test_outline_heading_filter.py` | 过滤规则单测 |
| `backend/tests/unit/test_outline_quality_service.py` | 质量摘要单测 |
| `backend/tests/unit/test_outline_unified_infer.py` | 统一推断单测 |
| `backend/tests/integration/test_actual_bid_outline_quality.py` | 鼎信/夹具集成 |
| `frontend/src/services/actualBidParse.ts` | 类型扩展 |
| `frontend/src/pages/OutlineCenter/index.tsx` | 待办质量列 |
| `frontend/src/pages/OutlineCenter/ActualBidParseConfirmWizard.tsx` | Alert + 只读过滤 Panel |

**Run tests from:** `backend/` with `../.venv/bin/pytest`

---

### Task 1: `outline_text_utils`

**Files:**
- Create: `backend/src/services/outline_text_utils.py`
- Test: `backend/tests/unit/test_outline_text_utils.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_outline_text_utils.py
import pytest

from src.services.outline_text_utils import effective_body_text


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", ""),
        ("   ", ""),
        ("# 标题", ""),
        ("一、报价表格式", "一、报价表格式"),
        ("1. 根据贵方采购文件要求我方承诺提供服务。", "1. 根据贵方采购文件要求我方承诺提供服务。"),
        ("![img](x.png)", ""),
        ("[image]", ""),
    ],
)
def test_effective_body_text(raw, expected):
    assert effective_body_text(raw) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_text_utils.py -v`  
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/services/outline_text_utils.py
from __future__ import annotations

import re

_IMAGE_PLACEHOLDER_RE = re.compile(r"^\[image\]$", re.IGNORECASE)
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")


def effective_body_text(text: str | None) -> str:
    if not text:
        return ""
    stripped = text.strip()
    if not stripped:
        return ""
    if _IMAGE_PLACEHOLDER_RE.match(stripped):
        return ""
    if _MARKDOWN_HEADING_RE.match(stripped):
        return stripped[_MARKDOWN_HEADING_RE.match(stripped).end() :].strip()
    return stripped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_text_utils.py -v`  
Expected: PASS (4 tests)

---

### Task 2: `outline_filter_rules.yaml` + `outline_heading_filter`

**Files:**
- Create: `backend/src/config/outline_filter_rules.yaml`
- Create: `backend/src/services/outline_heading_filter.py`
- Test: `backend/tests/unit/test_outline_heading_filter.py`

- [ ] **Step 1: Add config file**

```yaml
# backend/src/config/outline_filter_rules.yaml
quality:
  l1_ratio_warn: 0.6
  min_nodes_for_l1_warn: 30
  review_ratio_warn: 0.4
filter:
  body_list_min_length: 80
  date_line_max_length: 40
  parent_keywords_body_list:
    - 参选
    - 承诺
    - 声明
    - 响应函
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/unit/test_outline_heading_filter.py
from dataclasses import dataclass

import pytest

from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.outline_heading_filter import filter_outline_entries


@dataclass
class _Block:
    index: int
    block_type: str
    text: str
    style_name: str | None = None
    has_image: bool = False


def _entry(title: str, level: int = 1, temp_id: str = "n1", parent: str | None = None):
    return TocEntry(temp_id=temp_id, parent_temp_id=parent, title=title, level=level, sort_order=0)


def test_toc_strategy_keeps_all_entries():
    entries = [_entry("一、总则"), _entry("1. 很长的正文承诺" * 5, temp_id="n2")]
    result = filter_outline_entries(entries, blocks=[], strategy=ExtractStrategy.toc)
    assert len(result.kept) == 2
    assert result.stats.excluded == 0


def test_date_line_excluded():
    entries = [_entry("2026 年 5 月 19 日")]
    result = filter_outline_entries(entries, blocks=[], strategy=ExtractStrategy.content_heuristic)
    assert len(result.kept) == 0
    assert result.decisions[0].reason_code == "date_line"


def test_body_list_item_under_parent_keyword_excluded():
    parent = _entry("二、参选响应函", temp_id="n1")
    child = _entry(
        "1. 根据贵方采购文件要求，我方郑重承诺将按比选文件全部要求履行合同责任和义务。",
        level=1,
        temp_id="n2",
        parent="n1",
    )
    result = filter_outline_entries(
        [parent, child],
        blocks=[],
        strategy=ExtractStrategy.content_heuristic,
    )
    assert len(result.kept) == 1
    assert result.kept[0].title == "二、参选响应函"
    assert any(d.reason_code == "body_list_item" for d in result.decisions if d.action == "exclude")


def test_genuine_chapter_kept():
    entries = [_entry("一、报价表格式"), _entry("二、参选响应函", temp_id="n2")]
    result = filter_outline_entries(entries, blocks=[], strategy=ExtractStrategy.content_heuristic)
    assert len(result.kept) == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_heading_filter.py -v`  
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 4: Implement filter module**

```python
# backend/src/services/outline_heading_filter.py
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from pathlib import Path
from typing import Literal

import yaml

from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.heading_level_detector import detect_heading_level
from src.services.outline_text_utils import effective_body_text

logger = logging.getLogger(__name__)
_RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "outline_filter_rules.yaml"
_DATE_LINE_RE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月")


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


def _load_rules() -> dict:
    if not _RULES_PATH.exists():
        logger.warning("outline_filter_rules missing, using defaults path=%s", _RULES_PATH)
        return {
            "quality": {"l1_ratio_warn": 0.6, "min_nodes_for_l1_warn": 30, "review_ratio_warn": 0.4},
            "filter": {
                "body_list_min_length": 80,
                "date_line_max_length": 40,
                "parent_keywords_body_list": ["参选", "承诺", "声明", "响应函"],
            },
        }
    return yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8")) or {}


def _parent_title(entries_by_id: dict[str, TocEntry], parent_temp_id: str | None) -> str:
    if not parent_temp_id:
        return ""
    parent = entries_by_id.get(parent_temp_id)
    return parent.title if parent else ""


def _classify_entry(
    entry: TocEntry,
    *,
    strategy: ExtractStrategy,
    rules: dict,
    entries_by_id: dict[str, TocEntry],
    following_body: str,
) -> HeadingFilterDecision:
    filt = rules.get("filter", {})
    if strategy == ExtractStrategy.toc:
        return HeadingFilterDecision(entry.temp_id, "keep", "toc_native", entry.title, entry.level)

    detection = detect_heading_level(entry.title)
    if detection is not None and detection.confidence == "high" and detection.pattern == "heading_style":
        return HeadingFilterDecision(entry.temp_id, "keep", "heading_style_high", entry.title, entry.level)

    max_date_len = int(filt.get("date_line_max_length", 40))
    if len(entry.title) <= max_date_len and _DATE_LINE_RE.search(entry.title):
        return HeadingFilterDecision(entry.temp_id, "exclude", "date_line", entry.title, entry.level)

    parent_title = _parent_title(entries_by_id, entry.parent_temp_id)
    keywords = filt.get("parent_keywords_body_list") or []
    min_body_len = int(filt.get("body_list_min_length", 80))
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
    blocks: list,
    strategy: ExtractStrategy,
    block_text_by_heading_index: dict[int, str] | None = None,
) -> FilterResult:
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_heading_filter.py -v`  
Expected: PASS (4 tests)

---

### Task 3: `outline_quality_service`

**Files:**
- Create: `backend/src/services/outline_quality_service.py`
- Test: `backend/tests/unit/test_outline_quality_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_outline_quality_service.py
from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.outline_heading_filter import FilterStats
from src.services.outline_quality_service import summarize_outline_quality


def _entry(title: str, level: int):
    return TocEntry(temp_id="n1", parent_temp_id=None, title=title, level=level, sort_order=0)


def test_summarize_emits_high_l1_warning():
    entries = [_entry(f"章节{i}", 1) for i in range(40)]
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_quality_service.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement**

```python
# backend/src/services/outline_quality_service.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.services.docx_toc_extractor import ExtractStrategy, TocEntry
from src.services.outline_heading_filter import FilterStats

_RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "outline_filter_rules.yaml"


def _load_quality_rules() -> dict:
    if not _RULES_PATH.exists():
        return {"l1_ratio_warn": 0.6, "min_nodes_for_l1_warn": 30, "review_ratio_warn": 0.4}
    data = yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8")) or {}
    return data.get("quality", {})


def summarize_outline_quality(
    entries: list[TocEntry],
    *,
    strategy: ExtractStrategy,
    filter_stats: FilterStats,
    raw_count: int,
    needs_manual_review_count: int = 0,
) -> dict[str, Any]:
    node_count = len(entries)
    l1_count = sum(1 for e in entries if e.level == 1)
    max_depth = max((e.level for e in entries), default=0)
    l1_ratio = (l1_count / node_count) if node_count else 0.0
    review_ratio = (needs_manual_review_count / node_count) if node_count else 0.0

    rules = _load_quality_rules()
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
    }


def sample_excluded_decisions(decisions: list, limit: int = 20) -> list[dict[str, Any]]:
    excluded = [d for d in decisions if d.action == "exclude"]
    return [
        {
            "title": d.title[:200],
            "reason_code": d.reason_code,
            "level": d.level,
        }
        for d in excluded[:limit]
    ]
```

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_quality_service.py -v`  
Expected: PASS

---

### Task 4: 统一 walk / extract 推断快照

**Files:**
- Modify: `backend/src/services/docx_document_walker.py`
- Modify: `backend/src/services/docx_toc_extractor.py`
- Test: `backend/tests/unit/test_outline_unified_infer.py`

- [ ] **Step 1: Write failing test (mock collect to count calls)**

```python
# backend/tests/unit/test_outline_unified_infer.py
from unittest.mock import patch

from src.services.docx_content_collector import CollectResult, RawBlock
from src.services.docx_document_walker import DocumentWalkResult, walk_document
from src.services.docx_hierarchy_inferrer import InferResult, InferredHeading
from src.services.docx_toc_extractor import extract_toc_entries


def test_extract_toc_entries_reuses_infer_snapshot_without_second_collect(tmp_path):
    docx = tmp_path / "tiny.docx"
    # use existing fixture if present; else skip in CI — see integration task
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "sample-chinese-outline.docx"
    if not fixture.exists():
        import pytest
        pytest.skip("fixture missing")
    walked = walk_document(fixture)
    assert walked.collected is not None
    assert walked.infer_result is not None

    with patch("src.services.docx_toc_extractor.collect_content") as mock_collect:
        result = extract_toc_entries(fixture, infer_snapshot=walked)
        mock_collect.assert_not_called()
    assert len(result.entries) > 0
```

Add at top: `from pathlib import Path`

- [ ] **Step 2: Extend `DocumentWalkResult`**

In `docx_document_walker.py`:

```python
from src.services.docx_content_collector import CollectResult, collect_content

@dataclass
class DocumentWalkResult:
    nodes: list[WalkedNode]
    used_flat_fallback: bool = False
    needs_manual_review: bool = False
    infer_result: InferResult | None = None
    collected: CollectResult | None = None  # NEW
```

In `walk_document`, after `collected = collect_content(file_path)`:

```python
return DocumentWalkResult(
    nodes=materialized.nodes,
    used_flat_fallback=materialized.used_flat_fallback,
    needs_manual_review=materialized.needs_manual_review,
    infer_result=inferred,
    collected=collected,
)
```

- [ ] **Step 3: Extend `extract_toc_entries`**

In `docx_toc_extractor.py`:

```python
from src.services.docx_document_walker import DocumentWalkResult

def _entries_from_snapshot(snapshot: DocumentWalkResult) -> TocExtractResult:
    if snapshot.infer_result is None or snapshot.collected is None:
        raise ValueError("infer_snapshot missing infer_result or collected")
    nodes = materialize_outline_nodes(snapshot.infer_result, snapshot.collected.blocks)
    entries = [
        TocEntry(
            temp_id=node.temp_id,
            parent_temp_id=node.parent_temp_id,
            title=node.title,
            level=node.level,
            sort_order=node.sort_order,
        )
        for node in nodes
    ]
    strategy = _resolve_fallback_strategy(snapshot.infer_result)
    return TocExtractResult(entries=entries, strategy=strategy)


def extract_toc_entries(
    path: str | Path,
    *,
    infer_snapshot: DocumentWalkResult | None = None,
) -> TocExtractResult:
    file_path = Path(path)
    toc_entries = _extract_toc_entries_from_docx_xml(file_path)
    if toc_entries:
        return TocExtractResult(entries=toc_entries, strategy=ExtractStrategy.toc)
    if infer_snapshot is not None:
        return _entries_from_snapshot(infer_snapshot)
    return _to_fallback_entries(file_path)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_unified_infer.py tests/unit/test_docx_toc_extractor.py -v`  
Expected: PASS

---

### Task 5: Runner 接线 + suggestion payload

**Files:**
- Modify: `backend/src/services/actual_bid_parse_runner.py`

- [ ] **Step 1: Write failing integration test stub**

```python
# backend/tests/integration/test_actual_bid_outline_quality.py
import json
from pathlib import Path

import pytest

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "dingxin-golden-titles.json"


@pytest.mark.skipif(not GOLDEN.exists(), reason="golden titles fixture not committed yet")
def test_dingxin_golden_titles_retention():
    titles = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(titles) >= 20
```

- [ ] **Step 2: Create golden titles fixture**

```json
[
  "一、报价表格式",
  "二、参选响应函",
  "1.参选人业绩",
  "2.企业资质",
  "3.企业实力",
  "一、温度控制",
  "二、分类储存",
  "七、 附则",
  "1.1 目的",
  "6.1.1供应链稳定性保障"
]
```

Save to `backend/tests/fixtures/dingxin-golden-titles.json` (extend to ≥20 entries from鼎信 API sample).

- [ ] **Step 3: Wire runner** — in `_run_entry` replace:

```python
toc_result = extract_toc_entries(docx_path)
```

with:

```python
from src.services.outline_heading_filter import filter_outline_entries
from src.services.outline_quality_service import sample_excluded_decisions, summarize_outline_quality

raw_toc = extract_toc_entries(docx_path, infer_snapshot=walked)
filter_result = filter_outline_entries(
    raw_toc.entries,
    blocks=walked.collected.blocks if walked.collected else [],
    strategy=raw_toc.strategy,
)
outline_quality = summarize_outline_quality(
    filter_result.kept,
    strategy=raw_toc.strategy,
    filter_stats=filter_result.stats,
    raw_count=len(raw_toc.entries),
)
toc_result = TocExtractResult(entries=filter_result.kept, strategy=raw_toc.strategy)
# stash for suggestion:
task._outline_filter_decisions = filter_result.decisions  # or local vars passed to _persist_parse_suggestion
```

Extend `_persist_parse_suggestion` signature to accept `outline_quality` and `filter_decisions`; merge into `suggestion.payload`:

```python
"outline_quality": outline_quality,
"filter_decisions_sample": sample_excluded_decisions(filter_decisions),
"filtered_total": outline_quality["filter_stats"]["excluded"],
```

- [ ] **Step 4: Run integration tests**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_actual_bid_parse_runner.py tests/integration/test_actual_bid_outline_quality.py -v`  
Expected: PASS (integration may skip dingxin without local docm)

---

### Task 6: API 扩展

**Files:**
- Modify: `backend/src/api/routes/actual_bid_parse.py`
- Modify: `backend/src/api/routes/bid_outlines.py`
- Test: extend `backend/tests/contract/test_actual_bid_document_get.py` or add `test_outline_quality_api.py`

- [ ] **Step 1: Add helper to load suggestion quality**

```python
# in actual_bid_parse.py
def _outline_quality_from_suggestion(suggestion: DocumentParseSuggestion | None) -> dict | None:
    if suggestion is None or not isinstance(suggestion.payload, dict):
        return None
    return suggestion.payload.get("outline_quality")


def _filtered_meta_from_suggestion(suggestion: DocumentParseSuggestion | None) -> dict:
    if suggestion is None or not isinstance(suggestion.payload, dict):
        return {"filtered_total": 0, "filtered_nodes_sample": []}
    return {
        "filtered_total": suggestion.payload.get("filtered_total", 0),
        "filtered_nodes_sample": suggestion.payload.get("filter_decisions_sample", []),
    }
```

- [ ] **Step 2: Enrich list/detail task responses**

Join `FileImport` for `file_name`; join latest `DocumentParseSuggestion` by `parse_task_id`.

Add to each item:

```python
"file_name": file_import.file_name if file_import else None,
"outline_quality": _outline_quality_from_suggestion(suggestion),
**_filtered_meta_from_suggestion(suggestion),
```

- [ ] **Step 3: Contract test**

```python
def test_parse_task_detail_includes_outline_quality(client, seeded_kb, ready_task):
    resp = client.get(f"/api/v1/kbs/{kb_id}/actual-bid-parse/tasks/{task_id}", headers=HEADERS)
    data = resp.json()["data"]
    assert "outline_quality" in data
    assert "filtered_total" in data
```

- [ ] **Step 4: Run contract tests**

Run: `cd backend && ../.venv/bin/pytest tests/contract/test_actual_bid_document_get.py -v -k quality`  
(or new file)

---

### Task 7: 前端 — 目录中心 + 确认向导（方案 A）

**Files:**
- Modify: `frontend/src/services/actualBidParse.ts`
- Modify: `frontend/src/pages/OutlineCenter/index.tsx`
- Modify: `frontend/src/pages/OutlineCenter/ActualBidParseConfirmWizard.tsx`

- [ ] **Step 1: Extend TypeScript types**

```typescript
export interface OutlineQualitySummary {
  node_count: number;
  l1_ratio: number;
  max_depth: number;
  warnings: string[];
  extract_strategy: string;
  filter_stats?: { excluded: number; kept: number; by_reason?: Record<string, number> };
}

export interface FilteredNodeSample {
  title: string;
  reason_code: string;
  level: number;
}

// extend ActualBidParseTaskListItem:
  file_name?: string | null;
  outline_quality?: OutlineQualitySummary | null;
  filtered_total?: number;
  filtered_nodes_sample?: FilteredNodeSample[];
```

- [ ] **Step 2: Update OutlineCenter todo columns**

Replace UUID-only columns with:

```typescript
{ title: "文件名", dataIndex: "file_name", key: "file_name", ellipsis: true },
{
  title: "节点 / L1%",
  key: "quality",
  render: (_, r) => {
    const q = r.outline_quality;
    if (!q) return "—";
    return `${q.node_count} / ${Math.round(q.l1_ratio * 100)}%`;
  },
},
{
  title: "警告",
  key: "warnings",
  render: (_, r) =>
    (r.outline_quality?.warnings ?? []).map((w) => <Tag key={w} color="warning">{w}</Tag>),
},
```

- [ ] **Step 3: Wizard Step 2 — Alert + Collapse Panel**

In `ActualBidParseConfirmWizard.tsx` when `currentStep === 1`:

```tsx
{taskDetail?.outline_quality?.warnings?.length ? (
  <Alert
    type="warning"
    showIcon
    message="目录质量提示"
    description={`策略 ${taskDetail.outline_quality.extract_strategy}；L1 占比 ${Math.round(taskDetail.outline_quality.l1_ratio * 100)}%`}
  />
) : null}
{(taskDetail?.filtered_total ?? 0) > 0 ? (
  <Collapse
    items={[{
      key: "filtered",
      label: `已自动过滤 ${taskDetail.filtered_total} 条非章节内容（只读）`,
      children: (
        <Table
          size="small"
          pagination={false}
          dataSource={taskDetail.filtered_nodes_sample ?? []}
          columns={[
            { title: "标题", dataIndex: "title", ellipsis: true },
            { title: "原因", dataIndex: "reason_code", width: 140 },
            { title: "层级", dataIndex: "level", width: 60 },
          ]}
          rowKey={(r, i) => `${r.title}-${i}`}
        />
      ),
    }]}
  />
) : null}
```

- [ ] **Step 4: Manual smoke**

1. `./scripts/start.sh`
2. 打开 `/outlines` — 待办显示文件名与 L1%
3. 进入确认向导 Step 2 — 见过滤折叠面板

---

### Task 8: 鼎信回归 + 全量测试

**Files:**
- Modify: `backend/tests/integration/test_actual_bid_outline_quality.py`
- Modify: `specs/005-outline-extraction-quality/quickstart.md`（若命令需更新）

- [ ] **Step 1: Full regression test (local docm path via env)**

```python
@pytest.mark.skipif(not os.getenv("DINGXIN_DOCM"), reason="set DINGXIN_DOCM=/path/to/鼎信餐补标书.docm")
def test_dingxin_node_reduction_and_golden_retention(db_session, ...):
    # trigger parse or call filter on cached toc entries
    # assert node_count <= 302
    # assert golden retention >= 95%
```

- [ ] **Step 2: Run full suite**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_*.py tests/integration/test_actual_bid_outline_quality.py -v`

- [ ] **Step 3: Execute quickstart scenarios 1–7**

See `specs/005-outline-extraction-quality/quickstart.md`

---

## Spec Coverage Self-Review

| Requirement | Task |
|-------------|------|
| FR-001 structural_only | Task 2 |
| FR-002 日期/列举过滤 | Task 2 |
| FR-003 reason_code | Task 2, 5 |
| FR-004 质量摘要持久化 | Task 3, 5 |
| FR-005 警告展示 | Task 3, 7 |
| FR-006 parent_id | 已在 P0；Task 8 回归 |
| FR-007 统一推断 | Task 4 |
| FR-008 TOC 优先 | Task 2 `toc_native` 豁免 |
| FR-009 只读过滤展示 | Task 7 方案 A |
| FR-010 API 透传 | Task 6 |
| FR-011 鼎信基准 | Task 5, 8 |
| FR-012 脏 ready 过滤 | 已实现；Task 6 契约验证 |
| SC-001 ~ SC-006 | Task 8 |

**Placeholder scan:** 无 TBD/TODO/implement later。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-14-outline-extraction-quality.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派发独立 subagent，任务间做两阶段 review，迭代快  
2. **Inline Execution** — 本会话用 `executing-plans` 按 Task 批量执行，检查点停顿

**Which approach?**
