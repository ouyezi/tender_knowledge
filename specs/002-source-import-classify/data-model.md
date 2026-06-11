# Data Model: Epic 1 来源导入与文件分类确认

**Date**: 2026-06-11  
**Feature**: `specs/002-source-import-classify`

## Overview

```text
Knowledge Base (kb)
  ├── File Import
  │     ├── File Purpose Suggestion (1:1, pre-confirm)
  │     ├── parent_import_id → File Import (version chain)
  │     └── ↔ Classification Reference (post-confirm)
  ├── Import Task (file_import | file_purpose_classify)
  ├── Downstream Task Entry (post-confirm, Epic 2/3 消费)
  └── Import Audit Log
```

所有实体按 `kb_id` 隔离。

---

## Entity: File Import

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| import_id | UUID PK | | |
| kb_id | UUID FK | NOT NULL | |
| file_name | string(512) | NOT NULL | 原始文件名 |
| file_type | enum | docx/pdf/ppt/xlsx/image/other | 由扩展名推断 |
| file_size | bigint | NOT NULL, > 0 | bytes |
| file_hash | string(64) | nullable | SHA-256 hex |
| hash_status | enum | computed/unavailable/failed | |
| storage_path | string(1024) | NOT NULL | 相对 STORAGE_ROOT |
| file_purpose | enum | nullable until confirm | 见 FR-003 |
| product_category_ids | UUID[] | default [] | 确认后正式值 |
| chapter_taxonomy_id | UUID FK | nullable | 确认后正式值 |
| target_object_type | enum | nullable | document/template_material/manual_asset/wiki/ignored |
| enter_parsing | boolean | default true | 是否进入解析 |
| status | enum | 见状态机 | |
| parent_import_id | UUID FK | nullable | 新版本链 |
| version_no | int | default 1 | 同 hash 链版本号 |
| duplicate_resolution | enum | nullable | skip/new_version/normal |
| confirmed_by | string | nullable | operator id |
| confirmed_at | timestamp | nullable | |
| version | int | default 1 | 乐观锁 |
| created_by | string | NOT NULL | |
| created_at | timestamp | | |
| updated_at | timestamp | | |

### file_purpose enum

`actual_bid` | `template_file` | `qualification` | `ppt_material` | `cover_guide` |
`writing_guide` | `wiki_source` | `other`

### status enum

```text
uploaded → need_confirm → confirmed → processing → completed
                      ↘ ignored
任意阶段 → failed（可 retry 回 uploaded/need_confirm）
```

- `uploaded`：已落盘，后台任务未结束。
- `need_confirm`：建议已就绪，等待人工确认。
- `confirmed`：用户已确认，下游任务已创建。
- `processing`：下游 Epic 已认领（Epic 2/3 写入，Epic 1 可预留）。
- `completed` / `failed` / `ignored`：终态或半终态。

### Validation rules

- `kb_id` MUST 存在且 KB 为 active（`kb_write_guard`）。
- 确认时 `product_category_ids` / `chapter_taxonomy_id` MUST 引用 **active** 分类。
- `file_purpose=other` 且 `enter_parsing=false` 时 `target_object_type` SHOULD 为 ignored。
- 物理 DELETE 禁止；忽略仅改 status。

### Indexes

- `UNIQUE (kb_id, file_hash)` WHERE `file_hash IS NOT NULL`
- `INDEX (kb_id, status, created_at DESC)`
- `INDEX (kb_id, file_name, file_size)` — 辅助去重

---

## Entity: File Purpose Suggestion

机器建议；确认前展示；确认后以 File Import 正式字段为准。

| Field | Type | Notes |
|-------|------|-------|
| suggestion_id | UUID PK | |
| import_id | UUID FK | UNIQUE |
| kb_id | UUID FK | |
| suggested_purpose | enum | nullable |
| purpose_confidence | float | 0–1 |
| suggested_product_category_ids | UUID[] | |
| suggested_chapter_taxonomy_id | UUID FK | nullable |
| suggestion_source | enum | rule/llm/hybrid |
| rationale | text | nullable | 可读解释 |
| content_snippet | text | nullable | 摘要片段 |
| created_at | timestamp | |
| updated_at | timestamp | |

---

## Entity: Import Task

| Field | Type | Notes |
|-------|------|-------|
| task_id | UUID PK | |
| kb_id | UUID FK | |
| import_id | UUID FK | |
| task_type | enum | file_import, file_purpose_classify |
| status | enum | pending, running, completed, failed |
| log_lines | jsonb | `[{ "ts", "level", "message" }]` |
| error_message | text | nullable |
| retry_count | int | default 0 |
| trace_id | UUID | |
| started_at | timestamp | nullable |
| finished_at | timestamp | nullable |
| created_at | timestamp | |

**INDEX** `(kb_id, import_id, task_type)`

---

## Entity: Downstream Task Entry

用途确认后创建的下游占位；Epic 2/3 worker 拉取 `pending` 条目。

| Field | Type | Notes |
|-------|------|-------|
| entry_id | UUID PK | |
| kb_id | UUID FK | |
| import_id | UUID FK | |
| task_type | enum | 见 research R5 |
| status | enum | pending, claimed, completed, failed, cancelled |
| payload | jsonb | file_purpose, paths, category ids |
| claimed_by | string | nullable | worker id |
| claimed_at | timestamp | nullable |
| created_at | timestamp | |
| updated_at | timestamp | |

**INDEX** `(kb_id, task_type, status)`

---

## Entity: Import Audit Log

| Field | Type | Notes |
|-------|------|-------|
| audit_id | UUID PK | |
| trace_id | UUID | |
| kb_id | UUID FK | |
| import_id | UUID FK | |
| operator_id | string | |
| action | enum | upload, suggest_ready, confirm, ignore, retry, duplicate_skip, duplicate_new_version, route |
| payload_summary | jsonb | |
| created_at | timestamp | |

---

## Classification Reference 扩展（Epic 0 表）

在 `classification_reference.object_type` 增加：

- `file_import`

确认保存时写入 product_category / chapter_taxonomy 引用，`source=manual|suggested`。

---

## State transition diagram

```text
                    ┌──────────┐
         upload     │ uploaded │
        ──────────► │          │
                    └────┬─────┘
                         │ async: hash + suggest
                         ▼
                  ┌──────────────┐
                  │ need_confirm │
                  └──────┬───────┘
           confirm       │         ignore
              ┌──────────┼──────────┐
              ▼                     ▼
       ┌────────────┐        ┌──────────┐
       │ confirmed  │        │ ignored  │
       └─────┬──────┘        └──────────┘
             │ create downstream entries
             ▼
       ┌────────────┐
       │ processing │  (Epic 2/3)
       └─────┬──────┘
             ▼
    ┌────────────────┐
    │ completed/failed│
    └────────────────┘
```

---

## Relationships

```text
KnowledgeBase 1──* FileImport
FileImport 0..1──1 FilePurposeSuggestion
FileImport 0..1──* FileImport (parent_import_id)
FileImport 1──* ImportTask
FileImport 1──* DownstreamTaskEntry
FileImport 1──* ImportAuditLog
FileImport *──* ProductCategory (via product_category_ids + classification_reference)
FileImport *──0..1 ChapterTaxonomy
```

---

## Epic 2/3 预留（不在 Epic 1 建表）

- `documents`（import_id FK）
- `templates`（import_id FK）
- Candidate Knowledge 批次表

Epic 1 仅保证 `downstream_task_entries` 可被 Epic 2/3 查询消费。
