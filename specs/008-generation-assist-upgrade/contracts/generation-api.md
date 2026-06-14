# API Contract: Chapter Draft Generation

**Base path**: `/api/v1/kbs/{kb_id}/generation`  
**Version**: 1.0.0 (Epic 6)

**依赖 API**:

- [tender-requirement-api.md](./tender-requirement-api.md)
- [module-suggestion-api.md](../../007-outline-retrieval-module-suggestion/contracts/module-suggestion-api.md)

Header: `X-Operator-Id`（审计）。  
共用 envelope: `{ "code": "OK", "data": {...}, "trace_id": "uuid" }`

---

## Common enums

**task_status**: `pending` | `running` | `completed` | `failed`

**draft_outcome_status**: `pending` | `accepted` | `discarded`

**citation_source_type**: `tender_requirement` | `template_chapter` | `ku` | `wiki` | `manual_asset` | `variable`

---

## POST /drafts

创建章节草稿生成任务（异步）。

**Body**:

```json
{
  "requirement_context_id": "uuid",
  "suggestion_id": "uuid",
  "target_outline_node": {
    "title": "1.1 总体架构",
    "level": 2,
    "sort_order": 1
  },
  "product_category_ids": ["uuid"],
  "variable_values": {
    "project_name": "智慧园区一期",
    "customer_name": "某市住建局"
  },
  "user_chapter_selections": [
    {
      "template_chapter_id": "uuid",
      "enabled": true,
      "source": "user_manual"
    }
  ],
  "manual_asset_compliance": [
    { "manual_asset_id": "uuid", "status": "pass", "message": null },
    { "manual_asset_id": "uuid", "status": "missing", "message": "缺少 ISO9001 扫描件" }
  ],
  "confirm_adoption": false,
  "regenerate_from_draft_id": null
}
```

| Field | Required | Notes |
|-------|----------|-------|
| requirement_context_id | yes | |
| suggestion_id | yes | 须为 `adopted`，或 `draft` + `confirm_adoption=true` |
| target_outline_node | yes | |
| variable_values | no | 覆盖 TemplateVariable 默认值 |
| user_chapter_selections | no | 条件章节用户手工选择 |
| manual_asset_compliance | no | 合规校验结果消费 |
| regenerate_from_draft_id | no | 重新生成时引用旧 draft |

**Response `data`** (202 Accepted):

```json
{
  "task_id": "uuid",
  "status": "pending",
  "created_at": "2026-06-14T10:05:00Z"
}
```

**Errors**:

| Code | HTTP | When |
|------|------|------|
| MISSING_REQUIRED_VARIABLES | 422 | 必填变量未填；`details.missing_keys[]` |
| SUGGESTION_NOT_ADOPTED | 422 | suggestion 非 adopted 且未 confirm |
| LLM_UNAVAILABLE | 503 | LLM 未配置（同步预检） |
| ASSET_NOT_PUBLISHED | 422 | 引用了未发布/废弃资产 |
| NOT_FOUND | 404 | context/suggestion 不存在 |

---

## GET /tasks/{task_id}

查询生成任务状态。

**Response `data`**:

```json
{
  "task_id": "uuid",
  "status": "completed",
  "requirement_context_id": "uuid",
  "suggestion_id": "uuid",
  "target_outline_node": { "title": "1.1 总体架构", "level": 2, "sort_order": 1 },
  "draft_id": "uuid",
  "snapshot_id": "uuid",
  "error_code": null,
  "error_message": null,
  "started_at": "2026-06-14T10:05:01Z",
  "completed_at": "2026-06-14T10:05:45Z"
}
```

---

## GET /drafts/{draft_id}

查询章节草稿详情。

**Response `data`**:

```json
{
  "draft_id": "uuid",
  "task_id": "uuid",
  "snapshot_id": "uuid",
  "target_outline_node": { "title": "1.1 总体架构", "level": 2, "sort_order": 1 },
  "paragraphs": [
    {
      "paragraph_index": 0,
      "text": "本项目总体架构采用分层设计……",
      "citations": [
        {
          "source_type": "ku",
          "source_id": "uuid",
          "source_label": "历史技术方案-架构章节",
          "excerpt": "分层架构包括接入层、服务层……"
        },
        {
          "source_type": "tender_requirement",
          "source_id": "score_point:0",
          "source_label": "评分点：架构清晰可扩展",
          "excerpt": "架构清晰、可扩展，响应时间≤2秒"
        }
      ]
    }
  ],
  "conflict_hints": [
    {
      "type": "template_vs_rejection",
      "template_chapter_id": "uuid",
      "message": "模板章节含未响应资质说明，与废标项冲突",
      "severity": "high"
    }
  ],
  "missing_material_hints": [
    { "manual_asset_id": "uuid", "message": "缺少 ISO9001 扫描件" }
  ],
  "outcome_status": "pending",
  "version_tag": "v1",
  "is_active": true,
  "created_at": "2026-06-14T10:05:45Z"
}
```

---

## GET /drafts

按目标章节列表历史草稿。

**Query**: `target_title`, `requirement_context_id`, `outcome_status`, `is_active`, `page`, `page_size`

---

## POST /drafts/{draft_id}/regenerate

基于当前最新输入重新生成（创建新 task + 新 draft/snapshot）。

**Body**: 可选覆盖 `variable_values`, `user_chapter_selections`（缺省沿用上次 request_snapshot）

**Response**: 同 `POST /drafts`（新 task_id）

---

## POST /drafts/{draft_id}/accept

接受草稿为当前章节活跃稿。

**Response `data`**: `{ "draft_id", "outcome_status": "accepted", "outcome_at" }`

**Side effect**: 同 target_outline_node 下其他 `accepted` 稿 `is_active → false`（可选策略：保留 multiple accepted，以最新为准 — 实现时选「最新 accept 为 active」）。

---

## POST /drafts/{draft_id}/discard

废弃草稿。

**Response `data`**: `{ "draft_id", "outcome_status": "discarded", "is_active": false }`

---

## GET /snapshots/{snapshot_id}

查询 Generation Snapshot（审计）。

**Response `data`**:

```json
{
  "snapshot_id": "uuid",
  "task_id": "uuid",
  "requirement_context_id": "uuid",
  "requirement_context_snapshot": { },
  "suggestion_id": "uuid",
  "suggestion_snapshot": { },
  "target_outline_node": { },
  "used_ku_ids": ["uuid"],
  "used_wiki_ids": [],
  "used_template_chapter_ids": ["uuid"],
  "used_manual_asset_ids": [],
  "variable_inputs": { "project_name": "智慧园区一期" },
  "retrieval_trace_summary": { "trace_id": "uuid", "intent": "module_suggestion" },
  "prompt_version": "generation-v1.0.0",
  "result_version": "v1",
  "conflict_hints": [],
  "missing_material_hints": [],
  "input_priority_layers": {
    "rejection_clauses": 2,
    "score_points": 3,
    "template_hints": 1
  },
  "created_at": "2026-06-14T10:05:45Z"
}
```

---

## GET /snapshots

列表查询快照。

**Query**: `requirement_context_id`, `target_title`, `from`, `to`, `page`, `page_size`

---

## PATCH /module-suggestions/{suggestion_id}/adoption

（注册于 module_suggestions router，Epic 6 扩展）

**Body**:

```json
{
  "status": "adopted",
  "adoption_reason": "历史模块与评分点匹配度高"
}
```

**Response `data`**: `{ "suggestion_id", "status", "adopted_by", "adopted_at" }`

---

## Out of Scope (this API)

- Template Instance CRUD
- 完整招标文件上传解析
- 多章节批量联动生成
- 草稿自动 publish 为 KU/Wiki
- Word/PDF 导出
