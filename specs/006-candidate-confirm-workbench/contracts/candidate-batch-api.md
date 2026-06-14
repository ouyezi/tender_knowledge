# API Contract: Candidate Batch Confirm & Reject

**Base path**: `/api/v1/kbs/{kb_id}/candidates/batch`  
**Version**: 1.0.0 (Epic 4)

---

## POST /candidates/batch/confirm

批量确认发布。逐条调用与单条 confirm 相同的校验与 publish 编排；部分失败不影响成功项。

**Body**:

```json
{
  "items": [
    {
      "candidate_id": "doc_uuid1",
      "confirm_as": "ku",
      "product_category_ids": ["uuid"],
      "chapter_taxonomy_id": "uuid",
      "knowledge_type": "solution",
      "searchable": true,
      "review_comment": "批次 A"
    },
    {
      "candidate_id": "tpl_uuid2",
      "confirm_as": "template_chapter",
      "template_id": "uuid",
      "product_category_ids": [],
      "chapter_taxonomy_id": "uuid"
    }
  ],
  "batch_comment": "2026-06-14 晨间确认批次"
}
```

**Response `data`** (200，含部分失败):

```json
{
  "batch_id": "uuid",
  "trace_id": "uuid",
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "results": [
    {
      "candidate_id": "doc_uuid1",
      "status": "published",
      "confirmed_object_type": "ku",
      "confirmed_object_id": "uuid",
      "error": null
    },
    {
      "candidate_id": "tpl_uuid2",
      "status": "pending",
      "confirmed_object_type": null,
      "confirmed_object_id": null,
      "error": {
        "code": "PUBLISH_VALIDATION_FAILED",
        "message": "chapter_taxonomy_id inactive"
      }
    }
  ],
  "finished_at": "2026-06-14T10:05:00Z"
}
```

**Constraints**:

- 单次 batch MUST ≤ 100 items（MVP）；超过 → 413。
- 批量操作 MUST 在 30s 内返回汇总（SC-006）；内部可顺序处理，无需并行。

---

## POST /candidates/batch/reject

批量驳回（忽略）。

**Body**:

```json
{
  "candidate_ids": ["doc_uuid1", "doc_uuid2", "tpl_uuid3"],
  "review_comment": "低置信度批量忽略"
}
```

**Response `data`**:

```json
{
  "batch_id": "uuid",
  "trace_id": "uuid",
  "total": 3,
  "succeeded": 3,
  "failed": 0,
  "results": [
    {
      "candidate_id": "doc_uuid1",
      "status": "rejected",
      "error": null
    }
  ]
}
```

**Errors**:

| Code | HTTP | When |
|------|------|------|
| BATCH_TOO_LARGE | 413 | items > 100 |
| CANDIDATE_NOT_FOUND | 404 | 任一 ID 不存在（可选 strict 模式） |

---

## Audit

- 每条 batch 写一条 `batch_confirm` 或 `batch_reject` 审计头，`detail.items` 含逐条结果。
- `batch_id` 可用于操作日志筛选。
