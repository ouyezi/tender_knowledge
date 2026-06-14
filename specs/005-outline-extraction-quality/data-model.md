# Data Model: 标书目录提取质量增强

**Date**: 2026-06-14  
**Feature**: `specs/005-outline-extraction-quality`  
**Extends**: `specs/004-actual-bid-candidates/data-model.md`

## Overview

本特性**不新增数据库表**。在既有 Epic 3 实体上扩展 JSON 载荷与服务层值对象。

```text
Actual Bid Parse Task
  └── Document Parse Suggestion (payload 扩展 outline_quality)
        ├── outline_quality: OutlineQualitySummary
        └── filter_stats: FilterStats

Document Tree Node (既有字段语义扩展)
  └── is_outline_node / needs_manual_review / content_preview

Bid Outline + Bid Outline Node (过滤后子集)
  └── 节点数减少；parent_id 与 level 一致（FR-006，P0 已修复）

服务层值对象（非持久化表）
  ├── HeadingFilterDecision
  └── OutlineQualitySummary
```

---

## Value Object: HeadingFilterDecision

运行时结构，用于过滤流水线单节点决策。

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| temp_id | string | NOT NULL | 对应 OutlineNode.temp_id |
| action | enum | `keep` \| `exclude` \| `demote` | MVP 主要用 keep/exclude |
| reason_code | enum | 见下表 | 可解释性 |
| title | string | | 原始标题 |
| level | int | >= 1 | 推断层级 |
| parent_temp_id | string \| null | | |

**reason_code 枚举（MVP）**:

| Code | 含义 |
|------|------|
| `toc_native` | Word TOC 原生条目，豁免 |
| `heading_style_high` | Heading 样式高置信 |
| `date_line` | 日期行 |
| `body_list_item` | 正文长句列举 |
| `structural_only` | 纯结构无正文 |
| `default` | 默认保留 |

---

## Value Object: OutlineQualitySummary

嵌入 `document_parse_suggestions.payload.outline_quality`。

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| node_count | int | >= 0 | 过滤后 Bid Outline 节点数 |
| raw_candidate_count | int | >= 0 | 过滤前标题候选数 |
| max_depth | int | >= 1 | 最大 level |
| l1_count | int | >= 0 | level=1 节点数 |
| l1_ratio | float | 0.0–1.0 | l1_count / node_count |
| needs_manual_review_count | int | >= 0 | |
| review_ratio | float | 0.0–1.0 | review / node_count |
| extract_strategy | string | toc \| heading_heuristic \| content_heuristic \| flat_fallback | |
| warnings | string[] | | 如 `high_l1_ratio`, `flat_fallback`, `high_review_ratio` |
| filter_stats | object | | 见 FilterStats |

### Validation

- `node_count = 0` 时 `l1_ratio` 定义为 0，`warnings` 含 `empty_outline`。
- `warnings` 生成规则见 `outline_filter_rules.yaml` 与 research R4。

---

## Value Object: FilterStats

嵌入 `outline_quality.filter_stats`。

| Field | Type | Notes |
|-------|------|-------|
| excluded | int | exclude 计数 |
| kept | int | keep 计数 |
| by_reason | map[string]int | 按 reason_code 聚合 |

---

## Entity Extension: Document Parse Suggestion

**表**: `document_parse_suggestions`（无 schema migration）

`payload` JSON 扩展键：

```json
{
  "outline_extract_strategy": "content_heuristic",
  "walk_result": { "...": "..." },
  "hierarchy_inference": { "...": "..." },
  "outline_quality": { "...": "OutlineQualitySummary" },
  "filter_decisions_sample": [
    { "temp_id": "n12", "action": "exclude", "reason_code": "body_list_item", "title": "..." }
  ]
}
```

`filter_decisions_sample`：仅保留前 N 条（如 20）供排查，完整统计在 `filter_stats`。

---

## Entity Extension: Document Tree Node

**表**: `document_tree_nodes`（无新列）

| 字段 | 语义扩展 |
|------|----------|
| is_outline_node | true = 推断为标题候选（含被过滤者） |
| needs_manual_review | medium 置信或过滤 demote 时 true |
| content_preview | 用于 effective_body 判断；过滤不改写原文 |
| node_type | heading vs paragraph 不变 |

**规则**: 被 `exclude` 的标题候选仍以 `node_type=heading` 写入 Document Tree；
`persist_outline` 不为其创建 `bid_outline_nodes` 行。

---

## Entity Extension: Bid Outline / Bid Outline Node

无新字段。列表 API 可增加嵌套 `outline_quality`（来自最新 suggestion）。

| 约束 | 说明 |
|------|------|
| parent_id | 非根节点在含层级样例上 ≥70% 非空（SC-002） |
| title | 过滤后不得为空占位 |
| source_node_id | 指向 Document Tree heading 节点 |

---

## Entity Extension: Actual Bid Parse Task

**表**: `actual_bid_parse_tasks`（无新列）

行为约束（非列）：

| 规则 | 说明 |
|------|------|
| ready 列表 | `error_message IS NULL` AND `task_phase = full_pipeline`（FR-012） |
| llm_progress | MAY 追加 `outline_quality_computed: true` 日志条目 |

API 响应扩展字段 `outline_quality`（见 contracts），由 suggestion 联接填充。

---

## Configuration: outline_filter_rules.yaml

文件配置（非 DB），路径 `backend/src/config/outline_filter_rules.yaml`。

| 键 | 类型 | 默认 | 说明 |
|----|------|------|------|
| quality.l1_ratio_warn | float | 0.6 | L1 占比警告 |
| quality.min_nodes_for_l1_warn | int | 30 | 触发 L1 警告的最小节点数 |
| quality.review_ratio_warn | float | 0.4 | 待复核占比警告 |
| filter.body_list_min_length | int | 80 | 正文列举最小长度 |
| filter.date_line_max_length | int | 40 | 日期行最大长度 |
| filter.parent_keywords_body_list | string[] | 参选,承诺,声明,响应函 | 父章节关键词 |

---

## State / Flow

```text
walk_document
  → infer_snapshot
  → materialize outline candidates
  → outline_heading_filter (per-node HeadingFilterDecision)
  → filtered TocEntry[]
  → outline_quality_service.summarize()
  → persist_outline(filtered)
  → document_parse_suggestion.payload.outline_quality = summary
  → task.status = ready
```

重解析 + `structure_locked_at`：过滤仅作用于新 toc_entries / diff payload；
已确认节点不因过滤规则自动删除（Constitution III）。

---

## Indexes / Migration

**无 migration**。若未来 `filter_reason` 需落库到 `bid_outline_nodes`，单独立项，本特性不包含。

---

## Golden Test Data

| 文件 | 用途 |
|------|------|
| `tests/fixtures/dingxin-golden-titles.json` | SC-004 真章节保留率 |
| `tests/fixtures/sample-noisy-outline.docx` | CI 噪声过滤单测 |
| 鼎信餐补标书.docm（本地路径） | SC-001 集成回归 |
