# Data Model: Epic 6 生成辅助升级

**Date**: 2026-06-14  
**Feature**: `specs/008-generation-assist-upgrade`

## Overview

```text
Knowledge Base (kb)
  ├── Published Assets (Epic 2–4，只读消费)
  ├── Module Assembly Suggestion * (Epic 5 扩展 — 采纳状态)
  ├── Tender Requirement Context * (NEW — 服务层，非 KB 资产)
  ├── Generation Task * (NEW)
  ├── Chapter Draft * (NEW)
  └── Generation Snapshot * (NEW — append-only)

Epic 2 只读消费:
  TemplateVariable, TemplateRule, TemplateChapter
Epic 5 只读/扩展消费:
  ModuleAssemblySuggestion, RetrievalTrace, KnowledgePack snapshot
```

Epic 6 **不修改** Epic 2–4 正式资产核心语义；草稿为辅助输出，**不自动 publish** 为 KU/Wiki。

---

## Entity: Tender Requirement Context（NEW）

外部招标约束，服务层实体，不参与 retrieval_index。

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| requirement_context_id | UUID | PK | |
| kb_id | UUID | NOT NULL, INDEX | 关联 KB 便于列表过滤 |
| title | string(256) | NOT NULL | 用户可读名称，如「XX 项目招标约束」 |
| outline_structure | JSON | NOT NULL, default {} | 标书结构要求 |
| outline_nodes | JSON | NOT NULL, default [] | 章节标题与层级 `[{title, level, sort_order}]` |
| score_points | JSON | NOT NULL, default [] | 各章节评分点 `[{node_ref, text}]` |
| rejection_clauses | JSON | NOT NULL, default [] | 废标项字符串或结构化条目 |
| format_requirements | JSON | default [] | 格式要求 |
| qualification_requirements | JSON | default [] | 资质/证明材料要求 |
| response_clauses | JSON | default [] | 响应条款 |
| source_note | text | nullable | 外部系统/人工录入说明 |
| status | enum | active, archived | 软归档，不物理删除 |
| created_by | string | nullable | operator id |
| created_at | timestamptz | | |
| updated_at | timestamptz | | |

**INDEX** `(kb_id, status, created_at DESC)`

### Validation

- `outline_nodes` 每项 MUST 含 `title`；`level` ≥ 1。
- 允许 `score_points` / `rejection_clauses` 为空（edge case：标注缺失，不伪造）。

---

## Entity: Module Assembly Suggestion（EXTEND — Epic 5）

Epic 5 已有表；Epic 6 扩展字段：

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| requirement_context_id | UUID | FK → tender_requirement_contexts, nullable | 历史行可空 |
| status | enum | draft, adopted, rejected | default draft |
| adoption_reason | text | nullable | 用户采纳/拒绝备注 |
| adopted_by | string | nullable | |
| adopted_at | timestamptz | nullable | |

现有字段 `hit_reason` 保留作系统推荐理由；`tender_context_snapshot` 保留冗余快照。

### State transitions

```text
draft → adopted（用户确认采用）
draft → rejected（用户拒绝）
adopted → rejected（允许改判，记录新 adopted_at 清空）
```

生成请求 SHOULD 引用 `adopted` suggestion；`draft` 需 `confirm_adoption=true` 临时确认。

---

## Entity: Generation Task（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| task_id | UUID | PK | |
| kb_id | UUID | NOT NULL, INDEX | |
| requirement_context_id | UUID | FK, NOT NULL | |
| suggestion_id | UUID | FK → module_assembly_suggestions, nullable | |
| target_outline_node | JSON | NOT NULL | `{title, level, sort_order}` |
| status | enum | pending, running, completed, failed | |
| request_snapshot | JSON | NOT NULL | 完整 GenerationRequest 快照 |
| error_code | string(64) | nullable | LLM_UNAVAILABLE, GENERATION_FAILED, ... |
| error_message | text | nullable | |
| draft_id | UUID | FK → chapter_drafts, nullable | 完成时填充 |
| trace_id | UUID | nullable | 生成链路 trace |
| created_by | string | nullable | |
| started_at | timestamptz | nullable | |
| completed_at | timestamptz | nullable | |
| created_at | timestamptz | | |

**INDEX** `(kb_id, status, created_at DESC)`

---

## Entity: Chapter Draft（NEW）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| draft_id | UUID | PK | |
| kb_id | UUID | NOT NULL, INDEX | |
| task_id | UUID | FK → generation_tasks, UNIQUE | 1:1 |
| snapshot_id | UUID | FK → generation_snapshots, NOT NULL | |
| requirement_context_id | UUID | FK, NOT NULL | |
| suggestion_id | UUID | FK, nullable | |
| target_outline_node | JSON | NOT NULL | |
| paragraphs | JSON | NOT NULL, default [] | 见下方 schema |
| conflict_hints | JSON | default [] | 招标-模板冲突提示 |
| missing_material_hints | JSON | default [] | 缺失素材提示 |
| outcome_status | enum | pending, accepted, discarded | default pending |
| outcome_by | string | nullable | |
| outcome_at | timestamptz | nullable | |
| is_active | boolean | default true | 废弃后 false；历史可查 |
| version_tag | string(32) | NOT NULL | 如 v1, v2（同节点递增） |
| created_at | timestamptz | | |

### paragraphs JSON schema

```json
[
  {
    "paragraph_index": 0,
    "text": "段落正文（变量已替换）",
    "citations": [
      {
        "source_type": "tender_requirement | template_chapter | ku | wiki | manual_asset | variable",
        "source_id": "uuid-or-key",
        "source_label": "可读标签",
        "excerpt": "引用片段摘要"
      }
    ]
  }
]
```

### State transitions

```text
pending → accepted（用户接受为当前章节活跃稿）
pending → discarded（用户废弃）
accepted → discarded（允许废弃已接受稿）
重新生成 → 新 draft 行；旧 draft is_active=false（若被 supersede）
```

---

## Entity: Generation Snapshot（NEW — append-only）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| snapshot_id | UUID | PK | |
| kb_id | UUID | NOT NULL, INDEX | |
| task_id | UUID | FK, UNIQUE | |
| requirement_context_id | UUID | NOT NULL | |
| requirement_context_snapshot | JSON | NOT NULL | 冗余完整约束 |
| suggestion_id | UUID | nullable | |
| suggestion_snapshot | JSON | nullable | |
| target_outline_node | JSON | NOT NULL | |
| used_ku_ids | JSON | default [] | |
| used_wiki_ids | JSON | default [] | |
| used_template_chapter_ids | JSON | default [] | |
| used_manual_asset_ids | JSON | default [] | |
| variable_inputs | JSON | default {} | `{key: value}` |
| retrieval_trace_summary | JSON | nullable | Epic 5 trace 摘要 |
| prompt_version | string(64) | NOT NULL | 如 generation-v1.0.0 |
| result_version | string(64) | NOT NULL | 草稿 version_tag |
| conflict_hints | JSON | default [] | |
| missing_material_hints | JSON | default [] | |
| input_priority_layers | JSON | default {} | InputPriorityResolver 输出摘要 |
| created_at | timestamptz | | |

**规则**: 无 UPDATE 业务路径；仅 INSERT。

---

## Entity: Prompt Config Version（NEW — 可选轻量表）

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| prompt_version_id | UUID | PK | |
| name | string(128) | NOT NULL | generation-chapter-draft |
| version_tag | string(64) | NOT NULL | 1.0.0 |
| template_system | text | NOT NULL | |
| template_user | text | NOT NULL | |
| is_active | boolean | default false | |
| created_at | timestamptz | | |

初版可 seed 单条 `generation-v1.0.0`；snapshot 记录 `prompt_version` 字符串即可。

---

## Relationships

```text
TenderRequirementContext 1 ── * ModuleAssemblySuggestion
TenderRequirementContext 1 ── * GenerationTask
ModuleAssemblySuggestion 0..1 ── * GenerationTask
GenerationTask 1 ── 1 ChapterDraft
GenerationTask 1 ── 1 GenerationSnapshot
ChapterDraft * ── 1 GenerationSnapshot
```

---

## Validation Rules (cross-entity)

1. 生成输入引用的 KU/Wiki/Template Chapter/Manual Asset MUST `status=published`（或适用 confirmed）。
2. 未确认 Candidate Knowledge MUST NOT 出现在 `used_*_ids` 或 `paragraphs.citations`。
3. 必填 TemplateVariable 未填 → 不创建 GenerationTask（同步 422）。
4. `ConflictDetector` 标记冲突的 template_chapter MUST NOT 作为「已采用结构」写入 draft，
   仅可作为 reference hint 且 conflict_hints 非空。
5. 同一 `target_outline_node` + `kb_id` 可有多条 draft/snapshot；仅一条 `is_active=true AND outcome_status=accepted` 作为当前接受稿（业务层保证）。

---

## Migration Notes

- Epic 5 `module_assembly_suggestions` 加列 migration；现有行 `status=draft`，
  `requirement_context_id=null`。
- 新表 FK 指向 `knowledge_bases.kb_id`（若项目有 kb 表）或逻辑 kb_id 索引。
