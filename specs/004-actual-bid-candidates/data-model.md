# Data Model: Epic 3 实际标书导入与候选知识

**Date**: 2026-06-12  
**Feature**: `specs/004-actual-bid-candidates`

## Overview

```text
Knowledge Base (kb)
  ├── Document (↔ File Import, source_type=actual_bid)
  │     └── Document Tree Node * (tree + content blocks)
  ├── Bid Outline (↔ Document)
  │     └── Bid Outline Node * (tree; source_node_id → Document Tree Node)
  ├── Actual Bid Parse Task (↔ downstream entries ×3)
  ├── Document Parse Suggestion (per-node classification snapshot)
  ├── Bid Outline Structure Diff (re-parse vs locked outline)
  ├── Candidate Knowledge * (document-sourced, status=pending)
  ├── Chapter Pattern * (status=candidate, from mining task)
  └── Actual Bid Audit Log

Epic 2 (read-only consumer): Template Chapter → chapter_pattern_mining
Epic 2 (parallel): candidate_knowledge_stubs → aggregated in list API only
```

所有实体按 `kb_id` 隔离。`File Import` 来自 Epic 1，须 `file_purpose=actual_bid` 且已确认。

---

## Entity: Document

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| document_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| import_id | UUID FK | NOT NULL | → file_imports |
| source_type | enum | NOT NULL | MVP: `actual_bid` |
| source_usage | enum | default knowledge_extract | knowledge_extract / reference_only |
| product_category_ids | UUID[] | default [] | |
| bid_project_name | string(256) | nullable | |
| bid_customer_name | string(256) | nullable | |
| document_name | string(512) | NOT NULL | 默认文件名 |
| parse_status | enum | pending/parsing/ready/failed | |
| tree_version | int | default 1 | 重解析递增 |
| confirmed_metadata | boolean | default false | 来源元数据人工确认 |
| created_by | string | NOT NULL | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Validation

- `import_id` 对应 File Import MUST `file_purpose=actual_bid` 且 `status=confirmed`。
- 同一 `import_id` 活跃 Document 建议 UNIQUE（允许历史 deprecated 行）。
- 物理 DELETE 禁止。

**INDEX** `(kb_id, import_id)`  
**INDEX** `(kb_id, source_type, updated_at DESC)`

---

## Entity: Document Tree Node

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| node_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| document_id | UUID FK | NOT NULL | |
| parent_id | UUID FK | nullable | 根 null |
| node_type | enum | heading/paragraph/table/image/other | |
| title | string(512) | nullable | heading 必填 |
| level | int | nullable | heading 层级 |
| sort_order | int | NOT NULL, >= 0 | |
| content_ref | string(512) | nullable | 段落 hash 或 storage key |
| content_preview | text | nullable | 前 N 字符 |
| chapter_taxonomy_id | UUID FK | nullable | Epic 0 |
| product_category_ids | UUID[] | default [] | |
| is_outline_node | boolean | default false | 是否参与目录抽取 |
| candidate_template_chapter_id | UUID FK | nullable | 预留模板对齐 |
| candidate_pattern_id | UUID FK | nullable | 预留模式引用 |
| needs_manual_review | boolean | default false | |
| tree_version | int | NOT NULL | 与 document.tree_version 对齐 |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Validation

- KU 来源追溯以 **Document Tree Node** 为准（总需求 §6.12）。
- 编辑分类字段不触发 Bid Outline 自动更新。

**INDEX** `(document_id, parent_id, sort_order)`  
**INDEX** `(document_id, tree_version)`

---

## Entity: Bid Outline

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| bid_outline_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| source_doc_id | UUID FK | NOT NULL | → documents |
| import_id | UUID FK | NOT NULL | |
| outline_name | string(512) | NOT NULL | |
| outline_type | enum | default actual_bid | actual_bid / manual / … |
| product_category_ids | UUID[] | default [] | |
| project_name | string(256) | nullable | |
| customer_name | string(256) | nullable | |
| status | enum | draft/confirmed/published/deprecated | MVP 主要 draft→confirmed |
| extract_strategy | enum | toc/heading_heuristic/flat_fallback | |
| structure_locked_at | timestamp | nullable | 确认后写入 |
| structure_locked_by | string | nullable | |
| created_by | string | NOT NULL | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Validation

- 同一 `source_doc_id` 默认一个活跃 Bid Outline（重解析更新节点，不新建除非用户显式「新建目录」）。
- `status=confirmed` 后可被 Epic 5 只读消费（本 Epic 不实现检索）。

**INDEX** `(kb_id, source_doc_id)`  
**INDEX** `(kb_id, status, updated_at DESC)`

---

## Entity: Bid Outline Node

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| outline_node_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| bid_outline_id | UUID FK | NOT NULL | |
| parent_id | UUID FK | nullable | |
| title | string(512) | NOT NULL | |
| level | int | NOT NULL, >= 1 | |
| sort_order | int | NOT NULL, >= 0 | |
| chapter_taxonomy_id | UUID FK | nullable | |
| source_node_id | UUID FK | nullable | → document_tree_nodes |
| product_category_ids | UUID[] | default [] | |
| status | enum | draft/confirmed/deprecated | |
| needs_manual_review | boolean | default false | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Validation

- 目录匹配以 Bid Outline Node 为准（总需求 §6.12）。
- 合并/删除节点 MUST 写审计日志。

**INDEX** `(bid_outline_id, parent_id, sort_order)`  
**INDEX** `(bid_outline_id, source_node_id)`

---

## Entity: Actual Bid Parse Task

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| parse_task_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| import_id | UUID FK | NOT NULL | |
| document_id | UUID FK | nullable | 解析后填入 |
| bid_outline_id | UUID FK | nullable | 抽取后填入 |
| task_phase | enum | document_parse/bid_outline_extract/candidate_generate/full_pipeline | |
| status | enum | pending/running/ready/failed/cancelled | ready=可进入目录编辑 |
| parse_strategy | enum | docx | MVP |
| downstream_entry_ids | JSON | default [] | 关联三条 entry |
| error_message | text | nullable | |
| retry_count | int | default 0 | |
| llm_progress | JSON | nullable | total/completed/failed/degraded |
| trace_id | UUID | nullable | |
| started_at | timestamp | nullable | |
| finished_at | timestamp | nullable | |
| created_by | string | NOT NULL | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### State transitions

```text
pending → running → ready | failed
failed → pending (retry)
```

**INDEX** `(kb_id, import_id, status)`  
**INDEX** `(kb_id, created_at DESC)`

---

## Entity: Document Parse Suggestion

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| suggestion_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| parse_task_id | UUID FK | NOT NULL | |
| document_id | UUID FK | NOT NULL | |
| payload | JSON | NOT NULL | 节点级分类建议快照 |
| created_at | timestamp | | |

`payload` 结构示例：

```json
{
  "nodes": [
    {
      "node_id": "uuid",
      "suggested_chapter_taxonomy_id": "uuid",
      "suggested_product_category_ids": [],
      "confidence": 0.82,
      "suggestion_source": "rule"
    }
  ],
  "outline_extract_strategy": "toc"
}
```

---

## Entity: Bid Outline Structure Diff

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| diff_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| bid_outline_id | UUID FK | NOT NULL | |
| parse_task_id | UUID FK | NOT NULL | |
| diff_payload | JSON | NOT NULL | add/remove/move/rename |
| status | enum | pending/applied/rejected | |
| created_at | timestamp | | |
| resolved_at | timestamp | nullable | |
| resolved_by | string | nullable | |

---

## Entity: Candidate Knowledge

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| candidate_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| import_id | UUID FK | NOT NULL | |
| source_doc_id | UUID FK | NOT NULL | |
| source_node_id | UUID FK | NOT NULL | → document_tree_nodes |
| candidate_type | enum | ku/wiki/chapter_pattern/ignore | MVP: ku, wiki |
| title | string(512) | NOT NULL | |
| content | text | nullable | |
| summary | text | nullable | |
| suggested_knowledge_type | string(64) | nullable | solution, qualification, … |
| suggested_chapter_taxonomy_id | UUID FK | nullable | |
| suggested_product_category_ids | UUID[] | default [] | |
| confidence_score | float | nullable | |
| suggestion_source | string(16) | nullable | rule/llm/hybrid |
| status | enum | default pending | pending/confirmed/rejected/merged/published |
| parse_task_id | UUID FK | nullable | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Validation

- 本 Epic 仅创建 `status=pending`；确认/发布由 Epic 4 处理。
- MUST NOT 进入正式检索索引。

**INDEX** `(kb_id, status, created_at DESC)`  
**INDEX** `(kb_id, import_id)`  
**INDEX** `(source_doc_id, source_node_id)`

---

## Entity: Chapter Pattern

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| pattern_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| pattern_name | string(256) | NOT NULL | |
| chapter_taxonomy_id | UUID FK | nullable | |
| product_category_ids | UUID[] | default [] | |
| common_child_chapters | JSON | default [] | 子章节标题列表 |
| source_outline_ids | UUID[] | default [] | |
| source_template_chapter_ids | UUID[] | default [] | |
| frequency | int | default 0 | |
| status | enum | candidate/confirmed/deprecated | MVP: candidate |
| mining_task_id | UUID FK | nullable | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

---

## Entity: Chapter Pattern Mining Task

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| mining_task_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| status | enum | pending/running/completed/failed | |
| result_summary | JSON | nullable | patterns_created, clusters |
| error_message | text | nullable | |
| created_by | string | NOT NULL | |
| started_at | timestamp | nullable | |
| finished_at | timestamp | nullable | |
| created_at | timestamp | | |

---

## Entity: Actual Bid Audit Log

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| audit_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| action | string(64) | NOT NULL | parse_trigger, outline_edit, diff_apply, … |
| object_type | string(64) | NOT NULL | document, bid_outline, candidate_knowledge, … |
| object_id | UUID | NOT NULL | |
| operator_id | string | NOT NULL | |
| trace_id | UUID | nullable | |
| detail | JSON | default {} | |
| created_at | timestamp | | |

**INDEX** `(kb_id, object_type, object_id, created_at DESC)`

---

## Relationships

```text
File Import 1──1 Document (active)
Document 1──* Document Tree Node
Document 1──1 Bid Outline (active)
Bid Outline 1──* Bid Outline Node
Document Tree Node 1──0..1 Bid Outline Node (via source_node_id)
Document Tree Node 1──* Candidate Knowledge
Actual Bid Parse Task *──* Downstream Task Entry
Chapter Pattern Mining Task 1──* Chapter Pattern (candidate)
```

---

## Migration Notes

1. 新建表：`documents`, `document_tree_nodes`, `bid_outlines`, `bid_outline_nodes`,
   `actual_bid_parse_tasks`, `document_parse_suggestions`, `bid_outline_structure_diffs`,
   `candidate_knowledges`, `chapter_patterns`, `chapter_pattern_mining_tasks`,
   `actual_bid_audit_logs`.
2. **不修改** `candidate_knowledge_stubs` 结构；列表 API 聚合两源。
3. `classification_reference.object_type` 已含 `bid_outline`（Epic 0）；确认无需扩展。
