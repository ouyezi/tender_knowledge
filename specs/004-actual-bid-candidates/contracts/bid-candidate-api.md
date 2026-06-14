# API Contract: Candidate Knowledge (Read) & Chapter Pattern Mining

**Base paths**:

- `/api/v1/kbs/{kb_id}/candidates` — 候选知识只读列表（Epic 3）
- `/api/v1/kbs/{kb_id}/chapter-patterns` — 模式挖掘与候选列表

**Version**: 1.0.0 (Epic 3)

共用约定见 [product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

## Candidate Knowledge — GET /candidates

**只读**；本 Epic **不提供** confirm / merge / publish 端点（Epic 4）。

**Query**:

| Param | Notes |
|-------|-------|
| status | default `pending` |
| import_id | |
| source_doc_id | |
| candidate_type | ku, wiki |
| source_channel | document, template, all (default all) |
| page, page_size | |

**Response `data.items[]`**:

```json
{
  "candidate_id": "uuid",
  "source_channel": "document",
  "import_id": "uuid",
  "source_doc_id": "uuid",
  "source_node_id": "uuid",
  "candidate_type": "ku",
  "title": "云平台架构设计",
  "summary": "...",
  "suggested_knowledge_type": "solution",
  "suggested_chapter_taxonomy_id": "uuid",
  "suggested_product_category_ids": [],
  "confidence_score": 0.78,
  "status": "pending",
  "source_trace": {
    "file_name": "投标书.docx",
    "document_name": "投标书.docx",
    "node_title": "3.2 云平台架构"
  },
  "created_at": "2026-06-12T10:02:10Z"
}
```

`source_channel=template` 时条目来自 `candidate_knowledge_stubs`，字段映射为统一形状。

---

## Candidate Knowledge — GET /candidates/{candidate_id}

详情含 `content` 预览与完整 `source_trace`。

**Response `data`**:

```json
{
  "candidate_id": "uuid",
  "source_channel": "document",
  "title": "...",
  "content": "...",
  "summary": "...",
  "status": "pending",
  "source_trace": {
    "import_id": "uuid",
    "source_doc_id": "uuid",
    "source_node_id": "uuid",
    "parse_task_id": "uuid",
    "bid_outline_node_id": "uuid"
  }
}
```

---

## Chapter Pattern Mining — POST /chapter-patterns/mine

触发 `chapter_pattern_mining` 批任务。

**Body**:

```json
{
  "min_frequency": 2,
  "include_template_chapters": true
}
```

**Response `data`** (202):

```json
{
  "mining_task_id": "uuid",
  "status": "pending",
  "trace_id": "uuid"
}
```

---

## Chapter Pattern Mining — GET /chapter-patterns/mine/tasks/{mining_task_id}

**Response `data`**:

```json
{
  "mining_task_id": "uuid",
  "status": "completed",
  "result_summary": {
    "patterns_created": 5,
    "clusters_scanned": 120
  },
  "error_message": null,
  "finished_at": "2026-06-12T10:05:00Z"
}
```

---

## Chapter Pattern — GET /chapter-patterns

列出模式（默认 `status=candidate`）。

**Query**: `status`, `chapter_taxonomy_id`, `page`, `page_size`

**Response `data.items[]`**:

```json
{
  "pattern_id": "uuid",
  "pattern_name": "技术方案",
  "chapter_taxonomy_id": "uuid",
  "frequency": 8,
  "status": "candidate",
  "source_outline_ids": ["uuid"],
  "source_template_chapter_ids": ["uuid"],
  "common_child_chapters": ["总体架构", "安全方案"]
}
```

---

## Retrieval isolation

- 本 Epic 列表 API **仅供管理台浏览**。
- 检索服务（Epic 5）MUST NOT 索引 `status=pending` / `pending_confirm` 候选。
- 无 `POST /candidates/{id}/confirm` 等写操作。

---

## Errors

| Code | HTTP | When |
|------|------|------|
| CANDIDATE_NOT_FOUND | 404 | |
| MINING_IN_PROGRESS | 409 | 同 kb 已有 running mining 任务 |
| MINING_TASK_NOT_FOUND | 404 | |
