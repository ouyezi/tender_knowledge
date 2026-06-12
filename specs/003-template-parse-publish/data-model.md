# Data Model: Epic 2 模板库解析与发布

**Date**: 2026-06-12  
**Feature**: `specs/003-template-parse-publish`

## Overview

```text
Knowledge Base (kb)
  ├── Template Library
  │     └── Template *
  │           ├── Template Chapter * (tree)
  │           ├── Template Material *
  │           ├── Template Variable *
  │           └── Template Rule *
  ├── Template Parse Task (↔ File Import, ↔ Downstream Task Entry)
  ├── Template Parse Suggestion (1:1 per parse task, pre-confirm)
  ├── Template Structure Diff (re-parse vs locked tree)
  ├── Candidate Knowledge Stub (→ Epic 4)
  ├── Template Publish Snapshot
  └── Template Audit Log
```

所有实体按 `kb_id` 隔离。`File Import` 来自 Epic 1。

---

## Entity: Template Library

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| template_library_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| library_name | string(256) | NOT NULL | |
| library_type | enum | technical/commercial/qualification/product_specific/custom | |
| source_import_id | UUID FK | nullable | 首个关联导入 |
| product_category_ids | UUID[] | default [] | |
| owner | string | nullable | operator id |
| source_author | string | nullable | |
| source_updated_time | timestamp | nullable | 来自源文件元数据 |
| status | enum | draft/reviewing/published/deprecated | |
| version | string(32) | default "1.0" | 发布版本号 |
| version_no | int | default 1 | 递增 |
| published_at | timestamp | nullable | |
| published_by | string | nullable | |
| deprecated_at | timestamp | nullable | |
| created_by | string | NOT NULL | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Validation

- 发布时 MUST 至少含 0 个 Template（允许空库 draft）；推荐至少 1 个 published Template。
- 物理 DELETE 禁止；仅 `deprecated`。
- 仅 `status=published` 参与 Epic 5 推荐查询。

**INDEX** `(kb_id, status, updated_at DESC)`

---

## Entity: Template

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| template_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| template_library_id | UUID FK | **nullable** | null = 未归类模板 |
| source_import_id | UUID FK | NOT NULL | 解析来源 File Import |
| template_name | string(512) | NOT NULL | 默认取文件名 |
| template_type | enum | technical_bid/commercial_bid/qualification/chapter_set/custom | |
| product_category_ids | UUID[] | default [] | |
| applicable_project_types | string[] | default [] | MVP 可选 |
| applicable_customer_types | string[] | default [] | MVP 可选 |
| status | enum | draft/reviewing/published/deprecated | |
| version | string(32) | default "1.0" | |
| version_no | int | default 1 | |
| confirmed | boolean | default false | 解析人工确认后 true |
| structure_locked_at | timestamp | nullable | 确认后写入 |
| structure_locked_by | string | nullable | |
| published_at | timestamp | nullable | |
| published_by | string | nullable | |
| created_by | string | NOT NULL | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Validation

- `source_import_id` 对应 File Import MUST `file_purpose=template_file` 且已确认。
- 同一 `source_import_id` 活跃 Template 建议 UNIQUE（允许 deprecated 历史）。
- 重解析创建新 parse task，不新建 Template（更新同一 Template draft）除非用户显式「新建模板」。

**INDEX** `(kb_id, template_library_id, status)`  
**INDEX** `(kb_id, source_import_id)`

---

## Entity: Template Chapter

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| template_chapter_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| template_id | UUID FK | NOT NULL | |
| parent_id | UUID FK | nullable | 根节点 null |
| title | string(512) | NOT NULL | |
| level | int | NOT NULL, >= 1 | |
| sort_order | int | NOT NULL, >= 0 | 同级排序 |
| chapter_taxonomy_id | UUID FK | nullable | Epic 0 |
| product_category_ids | UUID[] | default [] | |
| expected_knowledge_types | string[] | default [] | MVP 可选 |
| bound_wiki_ids | UUID[] | default [] | 发布后绑定 |
| bound_ku_ids | UUID[] | default [] | |
| bound_material_ids | UUID[] | default [] | 冗余便捷；权威在 Material FK |
| variable_ids | UUID[] | default [] | |
| rule_ids | UUID[] | default [] | |
| required | boolean | default false | |
| is_fixed_section | boolean | default false | 固定模板章节 |
| ignored | boolean | default false | 确认忽略 |
| parse_source_ref | string(256) | nullable | docx 段落/锚点 |
| status | enum | draft/published/deprecated | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### Tree rules

- `(template_id, parent_id, sort_order)` 同级唯一。
- `level` MUST 与 parent.level + 1 一致（根 level=1）。
- 移动节点时级联更新子孙 `level`。
- `ignored=true` 节点不参与发布校验与推荐树。

**INDEX** `(template_id, parent_id, sort_order)`  
**INDEX** `(kb_id, chapter_taxonomy_id)`

---

## Entity: Template Material

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| material_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| template_id | UUID FK | NOT NULL | |
| template_chapter_id | UUID FK | nullable | |
| import_id | UUID FK | nullable | 源文件或附件导入 |
| material_type | enum | docx_section/ppt_material/image/table/fixed_paragraph/cover_guide/writing_guide/excel_table/other | |
| title | string(512) | nullable | |
| summary | text | nullable | |
| content | text | nullable | MVP 文本片段 |
| storage_path | string(1024) | nullable | 附件 |
| product_category_ids | UUID[] | default [] | |
| extract_as_candidate | boolean | default false | 确认后生成 stub |
| status | enum | draft/published/deprecated | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

---

## Entity: Template Variable

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| variable_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| template_id | UUID FK | NOT NULL | |
| template_chapter_id | UUID FK | nullable | |
| variable_key | string(128) | NOT NULL | 如 project_name |
| display_name | string(256) | nullable | |
| value_type | enum | string/number/date/enum/text | MVP 默认 string |
| required | boolean | default false | |
| default_value | text | nullable | |
| options | jsonb | default [] | enum 预留 |
| description | text | nullable | |
| placeholder_pattern | string(64) | default "{{key}}" | |
| status | enum | active/inactive | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

**UNIQUE** `(template_id, variable_key)`

---

## Entity: Template Rule

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| rule_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| template_id | UUID FK | NOT NULL | |
| template_chapter_id | UUID FK | nullable | |
| rule_type | enum | required/optional/product_match/(conditional/mutex/asset_reserved) | MVP 仅前三者可写 |
| condition | jsonb | nullable | product_match 时必填 |
| action | enum | enable/disable/warn/require_asset | MVP 主要 enable |
| message | text | nullable | |
| status | enum | active/inactive | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

---

## Entity: Template Parse Task

| Field | Type | Notes |
|-------|------|-------|
| parse_task_id | UUID PK | |
| kb_id | UUID FK | |
| import_id | UUID FK | |
| downstream_entry_id | UUID FK | nullable |
| template_id | UUID FK | nullable | 首次解析后绑定 |
| status | enum | pending/running/parse_ready/confirmed/failed/cancelled |
| parse_strategy | enum | docx/ppt/xlsx/pdf_fallback | 按 file_type |
| log_lines | jsonb | `[{ts, level, message}]` |
| error_message | text | nullable |
| retry_count | int | default 0 |
| trace_id | UUID | |
| started_at | timestamp | nullable |
| finished_at | timestamp | nullable |
| created_at | timestamp | |

**INDEX** `(kb_id, import_id, status)`  
**INDEX** `(kb_id, status, created_at)`

---

## Entity: Template Parse Suggestion

解析机器快照；确认后以 Template/Chapter 正式值为准。

| Field | Type | Notes |
|-------|------|-------|
| suggestion_id | UUID PK | |
| parse_task_id | UUID FK | UNIQUE |
| kb_id | UUID FK | |
| suggested_library_id | UUID FK | nullable |
| suggested_library_name | string | nullable | 新建库建议名 |
| suggested_product_category_ids | UUID[] | |
| suggested_chapter_tree | jsonb | 完整建议树 |
| suggested_materials | jsonb | |
| suggested_candidates | jsonb | |
| suggestion_source | enum | rule/llm/hybrid |
| rationale | text | nullable |
| created_at | timestamp | |

---

## Entity: Template Structure Diff

| Field | Type | Notes |
|-------|------|-------|
| diff_id | UUID PK | |
| kb_id | UUID FK | |
| template_id | UUID FK | |
| parse_task_id | UUID FK | 触发 diff 的新解析 |
| diff_payload | jsonb | added/removed/changed |
| status | enum | pending_review/applied/rejected |
| reviewed_by | string | nullable |
| reviewed_at | timestamp | nullable |
| created_at | timestamp | |

---

## Entity: Candidate Knowledge Stub

Epic 4 消费；Epic 2 只写 `pending_confirm`。

| Field | Type | Notes |
|-------|------|-------|
| stub_id | UUID PK | |
| kb_id | UUID FK | |
| import_id | UUID FK | |
| template_id | UUID FK | |
| template_chapter_id | UUID FK | nullable |
| material_id | UUID FK | nullable |
| candidate_type | enum | ku/wiki |
| title | string(512) | |
| summary | text | nullable |
| content_preview | text | nullable |
| product_category_ids | UUID[] | |
| chapter_taxonomy_id | UUID FK | nullable |
| status | enum | pending_confirm/confirmed/rejected |
| epic4_batch_id | UUID | nullable |
| created_at | timestamp | |
| updated_at | timestamp | |

---

## Entity: Template Publish Snapshot

| Field | Type | Notes |
|-------|------|-------|
| snapshot_id | UUID PK | |
| kb_id | UUID FK | |
| object_type | enum | template_library/template |
| object_id | UUID | library_id 或 template_id |
| version | string | |
| version_no | int | |
| snapshot_json | jsonb | 完整快照 |
| published_by | string | |
| published_at | timestamp | |

---

## Entity: Template Audit Log

| Field | Type | Notes |
|-------|------|-------|
| audit_id | UUID PK | |
| trace_id | UUID | |
| kb_id | UUID FK | |
| template_id | UUID FK | nullable |
| template_library_id | UUID FK | nullable |
| import_id | UUID FK | nullable |
| operator_id | string | |
| action | enum | parse_start/parse_complete/parse_fail/confirm/chapter_update/material_update/variable_update/rule_update/publish/deprecate/diff_apply/diff_reject |
| payload_summary | jsonb | |
| created_at | timestamp | |

---

## Classification Reference 扩展（Epic 0 表）

`object_type` 增加：

- `template_library`
- `template`
- `template_chapter`
- `template_material`

确认/发布时写入 product_category / chapter_taxonomy 引用。

---

## State Transitions

### Template Parse Task

```text
pending → running → parse_ready → confirmed
                 ↘ failed
parse_ready → running (retry)
```

### Template / Template Library

```text
draft → reviewing → published → deprecated
draft → published (MVP 允许跳过 reviewing)
```

### Re-parse with locked structure

```text
locked Template + new parse → template_structure_diff (pending_review)
  → applied | rejected
```

---

## Relationships

```text
KnowledgeBase 1──* TemplateLibrary
TemplateLibrary 0──* Template (nullable FK = 未归类)
FileImport 1──* Template
Template 1──* TemplateChapter (tree)
Template 1──* TemplateMaterial
Template 1──* TemplateVariable
Template 1──* TemplateRule
FileImport 1──* TemplateParseTask
TemplateParseTask 0..1──1 TemplateParseSuggestion
Template 1──* TemplateStructureDiff
Template 1──* CandidateKnowledgeStub
TemplateLibrary|Template 1──* TemplatePublishSnapshot
```

---

## Epic 4/5 接口面

| 消费者 | 查询条件 |
|--------|----------|
| Epic 4 | `candidate_knowledge_stubs.status=pending_confirm` |
| Epic 5 | `template_libraries.status=published` + chapters/materials published |
| Epic 6 | published templates + variables + rules |
