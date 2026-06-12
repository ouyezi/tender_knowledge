# API Contract: Template Parse

**Base path**: `/api/v1/kbs/{kb_id}/template-parse`  
**Version**: 1.0.0 (Epic 2)

共用 envelope、错误码、`X-Operator-Id`、`X-Trace-Id` 约定见
[product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

## Common enums

**parse_task_status**: `pending` | `running` | `parse_ready` | `confirmed` | `failed` | `cancelled`

**parse_strategy**: `docx` | `ppt` | `xlsx` | `pdf_fallback`

---

## POST /trigger

手动触发模板解析（或重试）。`import_id` 须已确认且 `file_purpose=template_file`。

**Body**:

```json
{
  "import_id": "uuid",
  "force_reparse": false
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| import_id | uuid | yes | File Import |
| force_reparse | boolean | no | true 时若已有 parse_ready/confirmed 则走 diff 或覆盖 draft |

**Flow**:

1. 校验 File Import 状态与用途。
2. 若存在 `running` 任务 → `409 PARSE_IN_PROGRESS`。
3. 创建 `template_parse_task`（`pending`）→ 异步执行。
4. 若有 pending downstream entry，关联 `downstream_entry_id` 并 mark claimed。

**Response `data`** (202):

```json
{
  "parse_task_id": "uuid",
  "import_id": "uuid",
  "template_id": "uuid",
  "status": "pending",
  "trace_id": "uuid"
}
```

---

## GET /tasks

分页列出解析任务。

**Query**: `import_id`, `status`, `page`, `page_size`

**Response `data.items[]`**:

```json
{
  "parse_task_id": "uuid",
  "import_id": "uuid",
  "template_id": "uuid",
  "status": "parse_ready",
  "parse_strategy": "docx",
  "error_message": null,
  "retry_count": 0,
  "started_at": "2026-06-12T10:00:00Z",
  "finished_at": "2026-06-12T10:00:30Z",
  "created_at": "2026-06-12T09:59:55Z",
  "llm_progress": {
    "total_chunks": 12,
    "completed_chunks": 12,
    "failed_chunks": 0,
    "degraded_to_rule": 2
  }
}
```

---

## GET /tasks/{parse_task_id}

任务详情 + 日志。

**Response `data`**:

```json
{
  "parse_task_id": "uuid",
  "import_id": "uuid",
  "template_id": "uuid",
  "status": "parse_ready",
  "log_lines": [
    { "ts": "2026-06-12T10:00:05Z", "level": "info", "message": "开始解析 docx" },
    { "ts": "2026-06-12T10:00:20Z", "level": "info", "message": "块级分类 12/12 完成" }
  ],
  "llm_progress": {
    "total_chunks": 12,
    "completed_chunks": 12,
    "failed_chunks": 0,
    "degraded_to_rule": 0
  },
  "suggestion": { "...": "见 GET /tasks/{id}/suggestion" },
  "structure_diff": null
}
```

若重解析产生 diff 且 `status=pending_review`，`structure_diff` 非 null。

---

## GET /tasks/{parse_task_id}/suggestion

获取机器解析建议（确认前）。

**Response `data`**:

```json
{
  "suggestion_id": "uuid",
  "suggested_library_id": null,
  "suggested_library_name": "餐补技术标模板库",
  "suggested_product_category_ids": ["uuid"],
  "suggested_chapter_tree": [
    {
      "temp_id": "n1",
      "parent_temp_id": null,
      "title": "1. 项目概述",
      "level": 1,
      "sort_order": 0,
      "chapter_taxonomy_id": "uuid",
      "product_category_ids": [],
      "suggested_product_category_ids": ["uuid"],
      "suggested_chapter_taxonomy_id": "uuid",
      "classification_confidence": 0.82,
      "suggestion_source": "hybrid",
      "classification_rationale": "标题命中售后服务；LLM 确认章节类型",
      "required": true,
      "is_fixed_section": true,
      "ignored": false
    }
  ],
  "suggested_materials": [
    {
      "temp_id": "m1",
      "chapter_temp_id": "n1",
      "material_type": "fixed_paragraph",
      "suggested_product_category_ids": [],
      "classification_confidence": 0.6,
      "suggestion_source": "rule"
    }
  ],
  "suggested_candidates": [
    {
      "temp_id": "c1",
      "candidate_type": "ku",
      "suggested_knowledge_type": "scheme",
      "suggested_product_category_ids": ["uuid"],
      "suggested_chapter_taxonomy_id": "uuid",
      "classification_confidence": 0.75,
      "suggestion_source": "llm"
    }
  ],
  "suggestion_source": "hybrid",
  "rationale": "块级规则+LLM；文件级不做细分类"
}
```

> **分类粒度**：`suggested_*` 数组中每一项为独立知识块及其分类建议。
> 文件级仅 Epic 1 `file_purpose`；本 API 不对整文件返回单一细粒度分类。

---

## POST /tasks/{parse_task_id}/confirm

人工确认解析结果。

**Body**:

```json
{
  "template_library_id": "uuid",
  "create_library": null,
  "template_name": "餐补技术标模板",
  "template_type": "technical_bid",
  "product_category_ids": ["uuid"],
  "chapters": [
    {
      "temp_id": "n1",
      "parent_temp_id": null,
      "title": "1. 项目概述",
      "level": 1,
      "sort_order": 0,
      "chapter_taxonomy_id": "uuid",
      "product_category_ids": [],
      "required": true,
      "is_fixed_section": true,
      "ignored": false
    }
  ],
  "materials": [
    {
      "temp_id": "m1",
      "chapter_temp_id": "n1",
      "material_type": "fixed_paragraph",
      "title": "固定说明",
      "extract_as_candidate": false,
      "ignored": false
    }
  ],
  "candidate_actions": [
    { "temp_id": "c1", "candidate_type": "ku", "accepted": true }
  ]
}
```

| Field | Notes |
|-------|-------|
| template_library_id | null = 未归类模板 |
| create_library | 可选 `{ "library_name", "library_type" }` 新建库并关联 |

**Response `data`** (200):

```json
{
  "parse_task_id": "uuid",
  "template_id": "uuid",
  "template_library_id": "uuid",
  "status": "confirmed",
  "structure_locked_at": "2026-06-12T10:05:00Z",
  "candidate_stubs_created": 2
}
```

---

## POST /tasks/{parse_task_id}/diff/apply

对已锁定 Template 应用待确认 diff。

**Body**: `{ "diff_id": "uuid", "resolution": "merge" | "reject" }`

**Response**: 更新后的 `template_id` + `structure_diff.status`

---

## POST /tasks/{parse_task_id}/retry

失败任务重试。仅 `status=failed` 可用。

**Response**: 新 `parse_task_id` 或复用原任务 `status=pending`

---

## Worker 内部（非 HTTP，文档化）

`template_parse_runner` 消费：

```sql
downstream_task_entries WHERE task_type='template_file_parse' AND status='pending'
```

**解析流水线**（澄清后）：

```text
1. docx_outline_parser + docx_content_extractor  → 知识块列表（无 LLM）
2. chunk_classification_service.classify(each chunk)  → 块级分类（可选 LLM，失败降级）
3. 更新 template_parse_tasks.llm_progress
4. 写入 template_parse_suggestions → parse_ready
```

约束：**禁止**将整份 docx 文本一次性送入 LLM（FR-022）。

claim 后执行解析，完成后 downstream `completed`；失败 `failed` 且 File Import 不变。
