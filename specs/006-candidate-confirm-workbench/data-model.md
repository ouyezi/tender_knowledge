# Data Model: Epic 4 候选知识确认工作台

**Date**: 2026-06-14  
**Feature**: `specs/006-candidate-confirm-workbench`

## Overview

```text
Knowledge Base (kb)
  ├── Candidate Knowledge * (document channel, pending → published/merged/rejected)
  ├── Candidate Knowledge Stub * (template channel, pending_confirm → ...)
  ├── Knowledge Unit * (NEW — published from candidate)
  ├── Wiki * (NEW)
  ├── Manual Asset * (NEW)
  ├── Template Chapter (existing — publish from template_chapter candidate)
  ├── Chapter Pattern (existing — candidate → confirmed)
  ├── Product Category (existing — publish from product_category candidate)
  └── Candidate Confirm Audit Log (NEW)
```

Epic 4 **扩展** Epic 3 候选表字段并 **新增** 正式知识层三表 + 审计表。不修改 Epic 2
`candidate_knowledge_stubs` 表名；通过适配器统一工作台 API。

---

## Entity: Candidate Knowledge（扩展）

在 Epic 3 `candidate_knowledges` 基础上 **新增/扩展** 字段：

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| confirmed_object_type | string(64) | nullable | ku, wiki, template_chapter, … |
| confirmed_object_id | UUID | nullable | 正式对象 PK |
| searchable | boolean | nullable | 发布时确认；KU/Wiki 默认 true |
| usage_hint | string(256) | nullable | 推荐使用方式 |
| review_comment | text | nullable | 最后一次确认备注 |
| merged_into_id | UUID FK | nullable | → candidate_knowledges |
| split_from_id | UUID FK | nullable | 拆分来源 |
| lineage | JSON | default {} | merge/split 来源链 |
| last_publish_error | text | nullable | 失败重试用 |
| publish_attempt_count | int | default 0 | |
| updated_by | string | nullable | 最后编辑者 |

### candidate_type enum（扩展）

```text
ku | wiki | template_chapter | manual_asset | chapter_pattern | product_category | ignore
```

### status enum（沿用 + 语义）

```text
pending → published | rejected | merged
pending → merged (split 来源归档)
published / rejected / merged 为终态（published 不可再编辑内容）
```

### Validation

- 仅 `status=pending` 可编辑内容与执行 merge/split/publish。
- `status=published` MUST 有 `confirmed_object_type` + `confirmed_object_id`。
- MUST NOT 进入检索索引（Epic 5 只索引正式表且 `searchable=true`）。

**INDEX** `(kb_id, suggested_chapter_taxonomy_id, status)`  
**INDEX** `(kb_id, confirmed_object_id)` WHERE confirmed_object_id IS NOT NULL

---

## Entity: Candidate Knowledge Stub（扩展）

与主表对齐的 Epic 4 字段（同名字段）：

| Field | Type | Notes |
|-------|------|-------|
| confirmed_object_type | string(64) | nullable |
| confirmed_object_id | UUID | nullable |
| searchable | boolean | nullable |
| usage_hint | string(256) | nullable |
| review_comment | text | nullable |
| merged_into_id | UUID | nullable → stub_id |
| split_from_id | UUID | nullable |
| lineage | JSON | default {} |
| last_publish_error | text | nullable |
| publish_attempt_count | int | default 0 |
| updated_by | string | nullable |

### candidate_type enum

扩展为与主表一致（含 template_chapter、manual_asset、product_category）。

### status enum（扩展）

```text
pending_confirm | published | rejected | merged
```

---

## Entity: Knowledge Unit（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| ku_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| title | string(512) | NOT NULL | |
| summary | text | nullable | |
| content | text | NOT NULL | |
| knowledge_type | string(64) | NOT NULL | solution, qualification, … |
| product_category_ids | UUID[] JSON | default [] | |
| chapter_taxonomy_id | UUID FK | nullable | |
| import_id | UUID FK | NOT NULL | |
| candidate_id | UUID | NOT NULL | 来源候选（document uuid） |
| source_doc_id | UUID FK | nullable | |
| source_node_id | UUID FK | nullable | |
| bid_outline_id | UUID FK | nullable | |
| template_library_id | UUID FK | nullable | 模板来源 KU |
| searchable | boolean | default true | |
| usage_hint | string(256) | nullable | |
| status | enum | published/deprecated | MVP 无 draft |
| version_no | int | default 1 | |
| version | string(32) | default "1.0" | |
| published_at | timestamp | | |
| published_by | string | NOT NULL | |
| deprecated_at | timestamp | nullable | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Validation

- 物理 DELETE 禁止；仅 deprecated。
- `candidate_id` + `kb_id` UNIQUE（幂等发布）。

**INDEX** `(kb_id, status, updated_at DESC)`  
**INDEX** `(kb_id, chapter_taxonomy_id)`  
**INDEX** `(kb_id, candidate_id)` UNIQUE

---

## Entity: Wiki（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| wiki_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| title | string(512) | NOT NULL | |
| summary | text | nullable | |
| content | text | NOT NULL | |
| wiki_type | string(64) | nullable | standard, faq, … |
| product_category_ids | UUID[] JSON | default [] | |
| chapter_taxonomy_id | UUID FK | nullable | |
| import_id | UUID FK | NOT NULL | |
| candidate_id | UUID | NOT NULL | |
| source_doc_id | UUID FK | nullable | |
| source_node_id | UUID FK | nullable | |
| searchable | boolean | default true | |
| usage_hint | string(256) | nullable | |
| status | enum | published/deprecated | |
| version_no | int | default 1 | |
| version | string(32) | default "1.0" | |
| published_at | timestamp | | |
| published_by | string | NOT NULL | |
| deprecated_at | timestamp | nullable | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

**INDEX** `(kb_id, status)`  
**INDEX** `(kb_id, candidate_id)` UNIQUE

---

## Entity: Manual Asset（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| manual_asset_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| title | string(512) | NOT NULL | |
| summary | text | nullable | |
| content | text | nullable | 文本型资质 |
| asset_type | string(64) | NOT NULL | license, certificate, authorization, … |
| storage_path | string(1024) | nullable | 文件型资质 |
| product_category_ids | UUID[] JSON | default [] | |
| import_id | UUID FK | NOT NULL | |
| candidate_id | UUID | NOT NULL | |
| source_doc_id | UUID FK | nullable | |
| valid_from | date | nullable | |
| valid_to | date | nullable | |
| searchable | boolean | default true | |
| status | enum | published/deprecated | |
| version_no | int | default 1 | |
| published_at | timestamp | | |
| published_by | string | NOT NULL | |
| deprecated_at | timestamp | nullable | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

**INDEX** `(kb_id, asset_type, status)`  
**INDEX** `(kb_id, candidate_id)` UNIQUE

---

## Entity: Published Template Chapter（复用 + 扩展）

发布 `confirm_as=template_chapter` 时写入既有 `template_chapters` 表，新增来源字段：

| Field | Type | Notes |
|-------|------|-------|
| candidate_id | UUID | nullable；发布时必填 |
| import_id | UUID FK | nullable |
| published_at | timestamp | |
| published_by | string | |

若 stub 通道发布：关联 `stub.template_id`，新建或更新章节节点（MVP：INSERT 新章节，
`status=published`）。

---

## Entity: Chapter Pattern（发布更新）

发布 `confirm_as=chapter_pattern`：

- 更新 `chapter_patterns.status`: candidate → confirmed
- 新增 `candidate_id` UUID nullable、`confirmed_at`、`confirmed_by`

---

## Entity: Product Category（发布创建）

发布 `confirm_as=product_category`：

- INSERT `product_categories`（category_name 来自候选 title，category_code 自动生成或
  管理员提交）
- 写 `candidate_id` 到扩展字段 `source_candidate_id`（nullable UUID）

---

## Entity: Candidate Confirm Audit Log（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| audit_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| candidate_id | string(128) | NOT NULL | doc_/tpl_ 复合 ID |
| batch_id | UUID | nullable | 批量操作关联 |
| action | enum | NOT NULL | edit, publish, publish_failed, ignore, merge, split, batch_confirm, batch_reject |
| operator_id | string | NOT NULL | |
| trace_id | UUID | NOT NULL | |
| detail | JSON | default {} | 含 confirm_as, object_id, errors, merged_ids, … |
| created_at | timestamp | | |

**INDEX** `(kb_id, candidate_id, created_at DESC)`  
**INDEX** `(kb_id, batch_id)`  
**INDEX** `(kb_id, action, created_at DESC)`

---

## State Transitions

### Candidate publish flow

```text
pending
  → [validate] → publish running (row lock)
  → published + confirmed_object_*
  |→ publish_failed (last_publish_error set, status stays pending)
  → retry → published
```

### Ignore flow

```text
pending → rejected (confirm_as=ignore)
```

### Merge flow

```text
source pending[] + target pending
  → sources.status=merged, merged_into_id=target
  → target.content updated, lineage.merged_from populated
```

---

## Relationships

```text
File Import 1──* Candidate Knowledge
File Import 1──* Candidate Knowledge Stub
Candidate Knowledge 1──0..1 Knowledge Unit (via candidate_id)
Candidate Knowledge 1──0..1 Wiki
Candidate Knowledge 1──0..1 Manual Asset
Candidate Knowledge Stub 1──0..1 Template Chapter
Candidate Knowledge 1──0..1 Chapter Pattern (confirm updates row)
Candidate Knowledge 1──0..1 Product Category
Candidate * 1──* Candidate Confirm Audit Log
```

---

## Migration Notes

1. **ALTER** `candidate_knowledges`：新增 confirmed/lineage/publish 字段；扩展 enum。
2. **ALTER** `candidate_knowledge_stubs`：同上 + status enum 扩展。
3. **CREATE** `knowledge_units`, `wikis`, `manual_assets`, `candidate_confirm_audit_logs`。
4. **ALTER** `template_chapters`, `chapter_patterns`, `product_categories`：来源 candidate 字段。
5. 不删除 Epic 3 数据；已有 pending 候选直接可确认。
