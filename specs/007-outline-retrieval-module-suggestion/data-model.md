# Data Model: Epic 5 目录级检索与模块建议

**Date**: 2026-06-14  
**Feature**: `specs/007-outline-retrieval-module-suggestion`

## Overview

```text
Knowledge Base (kb)
  ├── Published Assets (Epic 2–4 消费，只读索引源)
  │     KU / Wiki / Template / Template Chapter / Manual Asset
  │     Bid Outline / Bid Outline Node / Chapter Pattern
  ├── Retrieval Index Entry * (NEW — 统一检索索引)
  ├── Retrieval Strategy Version * (NEW)
  ├── Retrieval Trace * (NEW)
  ├── Retrieval Feedback * (NEW)
  ├── Retrieval Eval Set * (NEW)
  ├── Retrieval Eval Case * (NEW)
  ├── Module Assembly Suggestion * (NEW — Epic 6 消费)
  └── Chapter Gap Snapshot * (NEW — 可选缓存，或 trace 内 JSON)
```

Epic 5 **不修改** Epic 2–4 正式资产表核心语义；通过索引表与检索服务层聚合检索能力。
未确认候选 **MUST NOT** 进入 `retrieval_index_entries`。

---

## Entity: Retrieval Index Entry（NEW）

统一多态检索索引，支撑关键词、向量与元数据过滤。

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| index_entry_id | UUID | PK | |
| kb_id | UUID | NOT NULL, INDEX | |
| object_type | string(32) | NOT NULL | ku, wiki, template, template_chapter, bid_outline, bid_outline_node, chapter_pattern, manual_asset |
| object_id | UUID | NOT NULL | 多态 FK 逻辑引用 |
| title | string(512) | NOT NULL | 标准化后标题 |
| content_text | text | nullable | 摘要/正文拼接供 FTS |
| product_category_ids | JSON | default [] | |
| chapter_taxonomy_id | UUID | nullable | |
| knowledge_type | string(64) | nullable | KU/Wiki 等 |
| file_purpose | string(64) | nullable | |
| import_id | UUID | nullable | |
| source_doc_id | UUID | nullable | 追溯 |
| source_node_id | UUID | nullable | |
| bid_outline_id | UUID | nullable | |
| template_library_id | UUID | nullable | |
| metadata | JSON | default {} | 层级、sort_order、pattern frequency 等 |
| search_vector | tsvector | GENERATED/维护 | GIN 索引 |
| embedding | vector | nullable | pgvector；维度随 embedding 版本 |
| embedding_config_version | string(64) | nullable | |
| status | enum | published, deprecated | 与源对象同步 |
| indexed_at | timestamptz | | |
| updated_at | timestamptz | | |

**UNIQUE** `(kb_id, object_type, object_id)`  
**INDEX** `(kb_id, object_type, status)`  
**INDEX** GIN `(search_vector)`  
**INDEX** vector `(embedding) vector_cosine_ops`（pgvector）

### Validation

- 仅当源对象 `status=published`（或 chapter_pattern `confirmed`）且 `searchable=true`（适用类型）时写入。
- `object_type=bid_outline_node` 时 `metadata` MUST 含 `level`、`sort_order`、`parent_id`。

---

## Entity: Retrieval Strategy Version（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| strategy_version_id | UUID | PK | |
| kb_id | UUID | NOT NULL | 支持 KB 级策略；全局默认 kb_id 可空策略见 config |
| name | string(128) | NOT NULL | 如 default-v1 |
| version_tag | string(64) | NOT NULL | 语义版本 1.0.0 |
| config | JSON | NOT NULL | 见下方 schema |
| embedding_config_version | string(64) | nullable | |
| rerank_config_version | string(64) | nullable | |
| prompt_config_version | string(64) | nullable | |
| is_active | boolean | default false | 每 kb 仅一个 active |
| created_by | string | nullable | |
| created_at | timestamptz | | |
| notes | text | nullable | |

### config JSON schema（摘要）

```json
{
  "intents": {
    "knowledge_lookup": { "enable_bm25": true, "enable_vector": true, "enable_rerank": false, "top_k": 20 },
    "material_recommend": { "enable_bm25": true, "enable_vector": true, "enable_rerank": true, "top_k": 15 },
    "module_suggestion": { "enable_structure": true, "top_k": 10 },
    "trace_lookup": { "top_k": 1 }
  },
  "bm25_weights": { "title": 0.6, "content": 0.4 },
  "match_score_weights": {
    "product_category": 0.3,
    "chapter_taxonomy": 0.3,
    "title_similarity": 0.2,
    "level_order": 0.1,
    "knowledge_coverage": 0.1
  },
  "gap_threshold": { "min_frequency": 3, "min_ratio": 0.3 },
  "context_expand_depth": 1
}
```

---

## Entity: Retrieval Trace（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| trace_id | UUID | PK | 对外 trace_id |
| kb_id | UUID | NOT NULL, INDEX | |
| intent | string(32) | NOT NULL | knowledge_lookup, material_recommend, module_suggestion, trace_lookup, directory_match |
| strategy_version_id | UUID | FK | |
| request_snapshot | JSON | NOT NULL | 完整 RetrievalRequest |
| response_summary | JSON | nullable | 命中数、top ids、latency |
| stages | JSON | default {} | recall/rank 中间摘要 |
| status | enum | success, partial, failed | |
| error_message | text | nullable | |
| latency_ms | int | nullable | |
| operator_id | string | nullable | |
| created_at | timestamptz | INDEX | |

**INDEX** `(kb_id, intent, created_at DESC)`

---

## Entity: Retrieval Feedback（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| feedback_id | UUID | PK | |
| kb_id | UUID | NOT NULL | |
| trace_id | UUID | FK → retrieval_traces | |
| feedback_type | enum | NOT NULL | 见下方 |
| object_type | string(32) | nullable | 针对的单条结果 |
| object_id | UUID | nullable | |
| rank_position | int | nullable | 列表位置 |
| expected_object_ids | JSON | default [] | 漏召回补充 |
| comment | text | nullable | |
| filter_adjustment | JSON | nullable | 人工调整分类过滤 |
| operator_id | string | nullable | |
| created_at | timestamptz | | |

### feedback_type enum

```text
click | adopt | copy | add_to_draft | useful | not_useful | false_positive | false_negative
```

---

## Entity: Retrieval Eval Set（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| eval_set_id | UUID | PK | |
| kb_id | UUID | NOT NULL | |
| name | string(256) | NOT NULL | |
| description | text | nullable | |
| status | enum | draft, active, archived | |
| created_by | string | nullable | |
| created_at | timestamptz | | |
| updated_at | timestamptz | | |

---

## Entity: Retrieval Eval Case（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| eval_case_id | UUID | PK | |
| eval_set_id | UUID | FK | |
| kb_id | UUID | NOT NULL | |
| query | text | NOT NULL | |
| intent | string(32) | NOT NULL | |
| filters | JSON | default {} | |
| expected_object_ids | JSON | default [] | |
| negative_object_ids | JSON | default [] | |
| product_category_ids | JSON | default [] | |
| chapter_taxonomy_ids | JSON | default [] | |
| created_from | enum | manual, user_feedback, production_log | |
| source_feedback_id | UUID | nullable | FK → retrieval_feedbacks |
| confirmed_at | timestamptz | nullable | 反馈转用例门禁 |
| confirmed_by | string | nullable | |
| status | enum | pending, confirmed, rejected | |
| created_at | timestamptz | | |

### Validation

- `created_from=user_feedback` 且 `status=confirmed` MUST 有 `confirmed_at` + `confirmed_by`。
- 未 confirmed 的用例不参与正式评测执行。

---

## Entity: Module Assembly Suggestion（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| suggestion_id | UUID | PK | |
| kb_id | UUID | NOT NULL | |
| trace_id | UUID | FK | 关联生成 trace |
| target_outline_node | JSON | NOT NULL | title, level, sort_order 等 |
| suggested_template_chapter_ids | JSON | default [] | |
| suggested_ku_ids | JSON | default [] | |
| suggested_wiki_ids | JSON | default [] | |
| suggested_manual_asset_ids | JSON | default [] | |
| suggested_bid_outline_node_ids | JSON | default [] | |
| suggested_chapter_pattern_ids | JSON | default [] | |
| organization_hint | JSON | default {} | 顺序与组合 |
| match_score | float | NOT NULL | |
| coverage_rate | float | NOT NULL | |
| score_detail | JSON | default {} | |
| score_point_coverage | JSON | default [] | |
| rejection_risks | JSON | default [] | |
| risk_flags | JSON | default [] | |
| hit_reason | text | nullable | |
| knowledge_pack_snapshot | JSON | default [] | 扩展 Knowledge Pack 列表 |
| product_category_ids | JSON | default [] | |
| project_type | string(64) | nullable | |
| customer_type | string(64) | nullable | |
| tender_context_snapshot | JSON | nullable | |
| created_at | timestamptz | | |

**INDEX** `(kb_id, trace_id)`

---

## Entity: Retrieval Eval Run（NEW — 评测执行记录）

| Field | Type | Notes |
|-------|------|-------|
| eval_run_id | UUID | PK |
| kb_id | UUID | |
| eval_set_id | UUID | FK |
| strategy_version_id | UUID | FK |
| baseline_strategy_version_id | UUID | nullable | 对比用 |
| metrics | JSON | Recall@K, NDCG, … |
| comparison_metrics | JSON | nullable | A vs B 差异 |
| status | enum | running, success, failed |
| started_at / finished_at | timestamptz | |
| triggered_by | string | nullable |

---

## Relationships

```text
RetrievalStrategyVersion 1──* RetrievalTrace
RetrievalTrace 1──* RetrievalFeedback
RetrievalTrace 1──* ModuleAssemblySuggestion
RetrievalEvalSet 1──* RetrievalEvalCase
RetrievalEvalSet 1──* RetrievalEvalRun
RetrievalFeedback 0──1 RetrievalEvalCase (source_feedback_id)
RetrievalIndexEntry ──► Published Asset (logical polymorphic)
```

---

## State Transitions

### Retrieval Eval Case

```text
pending → confirmed (人工确认反馈转用例)
pending → rejected
confirmed → (终态，可编辑 expected ids)
```

### Retrieval Strategy Version

```text
创建 → is_active=false
激活 → 同 kb 其他版本 is_active=false，当前 true
```

### Module Assembly Suggestion

创建后不可变（审计）；新请求产生新 suggestion_id + trace_id。

---

## Index Sync Rules（与正式资产）

| 源事件 | 索引动作 |
|--------|----------|
| KU/Wiki/Manual Asset 发布 | UPSERT index entry |
| Template Chapter 发布 | UPSERT |
| Bid Outline / Node 确认发布 | UPSERT nodes + outline |
| Chapter Pattern confirmed | UPSERT |
| 资产 deprecated | index entry status=deprecated |
| searchable=false | 从活跃召回排除（或 status 标记） |
