# API Contract: Actual Bid Parse

**Base path**: `/api/v1/kbs/{kb_id}/actual-bid-parse`  
**Version**: 1.0.0 (Epic 3)

共用 envelope、错误码、`X-Operator-Id`、`X-Trace-Id` 约定见
[product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

## Common enums

**parse_task_status**: `pending` | `running` | `ready` | `confirmed` | `failed` | `cancelled`

**parse_task_phase**: `document_parse` | `bid_outline_extract` | `candidate_generate` | `full_pipeline`

**document_parse_status**: `pending` | `parsing` | `ready` | `failed`

---

## POST /trigger

手动触发实际标书解析（或重试整条流水线）。

**Body**:

```json
{
  "import_id": "uuid",
  "force_reparse": false,
  "phases": ["full_pipeline"]
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| import_id | uuid | yes | File Import |
| force_reparse | boolean | no | true 时若已有 ready 结果则走 outline diff |
| phases | string[] | no | 默认 `full_pipeline`；可单阶段重跑 |

**Flow**:

1. 校验 File Import `status=confirmed` 且 `file_purpose=actual_bid`。
2. 若存在 `running` 任务 → `409 PARSE_IN_PROGRESS`。
3. 创建 `actual_bid_parse_task` → 异步执行 downstream 链。
4. Claim `document_parse` / `bid_outline_extract` / `candidate_knowledge_generate` entries。

**Response `data`** (202):

```json
{
  "parse_task_id": "uuid",
  "import_id": "uuid",
  "document_id": "uuid",
  "status": "pending",
  "trace_id": "uuid"
}
```

---

## GET /tasks

分页列出实际标书解析任务。

**Query**: `import_id`, `status`, `page`, `page_size`

**Response `data.items[]`**:

```json
{
  "parse_task_id": "uuid",
  "import_id": "uuid",
  "document_id": "uuid",
  "bid_outline_id": "uuid",
  "task_phase": "full_pipeline",
  "status": "ready",
  "parse_strategy": "docx",
  "error_message": null,
  "retry_count": 0,
  "llm_progress": {
    "total_chunks": 24,
    "completed_chunks": 24,
    "failed_chunks": 0,
    "degraded_to_rule": 3
  },
  "started_at": "2026-06-12T10:00:00Z",
  "finished_at": "2026-06-12T10:02:15Z",
  "created_at": "2026-06-12T09:59:55Z"
}
```

---

## GET /tasks/{parse_task_id}

任务详情，含 `suggestion` 摘要（若 ready）。

**Response `data`**:

```json
{
  "parse_task_id": "uuid",
  "status": "ready",
  "document_id": "uuid",
  "bid_outline_id": "uuid",
  "suggestion": {
    "outline_extract_strategy": "toc",
    "node_count": 42,
    "candidate_count": 18,
    "needs_manual_review": true
  },
  "downstream_entries": [
    { "task_type": "document_parse", "status": "completed" },
    { "task_type": "bid_outline_extract", "status": "completed" },
    { "task_type": "candidate_knowledge_generate", "status": "completed" }
  ]
}
```

---

## POST /tasks/{parse_task_id}/confirm

解析确认向导提交：确认来源元数据与目录节点人工修订结果。

> 该端点仅将任务状态置为 `confirmed`，**不会**写入 `bid_outlines.structure_locked_at`。
> 目录结构锁定由 `POST /bid-outlines/{bid_outline_id}/confirm` 负责。

**Body**:

```json
{
  "document": {
    "bid_project_name": "某某项目",
    "bid_customer_name": "某某客户",
    "product_category_ids": ["uuid"]
  },
  "outline_nodes": [
    {
      "outline_node_id": "uuid",
      "parent_id": null,
      "title": "1. 技术方案",
      "level": 1,
      "sort_order": 0,
      "chapter_taxonomy_id": null,
      "product_category_ids": [],
      "needs_manual_review": false
    }
  ]
}
```

**Response `data`**:

```json
{
  "parse_task_id": "uuid",
  "document_id": "uuid",
  "bid_outline_id": "uuid",
  "status": "confirmed",
  "structure_locked_at": null,
  "updated_outline_nodes": 8
}
```

---

## GET /documents/{document_id}

Document 详情与来源元数据。

**Response `data`**:

```json
{
  "document_id": "uuid",
  "import_id": "uuid",
  "source_type": "actual_bid",
  "source_usage": "knowledge_extract",
  "product_category_ids": [],
  "bid_project_name": "某某项目",
  "bid_customer_name": "某某客户",
  "document_name": "投标书.docx",
  "parse_status": "ready",
  "tree_version": 1,
  "bid_outline_id": "uuid"
}
```

---

## PATCH /documents/{document_id}

更新来源元数据（项目名、客户名、产品分类）。

**Body** (partial):

```json
{
  "bid_project_name": "string",
  "bid_customer_name": "string",
  "product_category_ids": ["uuid"]
}
```

**Response `data`**: 更新后 Document 对象。

---

## GET /documents/{document_id}/tree

Document Tree（分页或 `max_depth` 限制大树）。

**Query**: `tree_version` (default latest), `node_type`, `max_depth`

**Response `data`**:

```json
{
  "document_id": "uuid",
  "tree_version": 1,
  "nodes": [
    {
      "node_id": "uuid",
      "parent_id": null,
      "node_type": "heading",
      "title": "1. 技术方案",
      "level": 1,
      "sort_order": 0,
      "chapter_taxonomy_id": null,
      "product_category_ids": [],
      "is_outline_node": true,
      "needs_manual_review": false,
      "content_preview": null
    }
  ]
}
```

---

## PATCH /documents/{document_id}/tree/nodes/{node_id}

更新 Document Tree Node 分类字段（不触发 Bid Outline 同步）。

**Body**:

```json
{
  "chapter_taxonomy_id": "uuid",
  "product_category_ids": ["uuid"],
  "is_outline_node": true
}
```

---

## Errors

| Code | HTTP | When |
|------|------|------|
| IMPORT_NOT_CONFIRMED | 400 | import 未确认或用途非 actual_bid |
| PARSE_IN_PROGRESS | 409 | 已有 running 任务 |
| DOCUMENT_NOT_FOUND | 404 | |
| PARSE_TASK_NOT_FOUND | 404 | |
