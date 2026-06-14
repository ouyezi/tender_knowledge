# API Contract: Candidate Confirm Audit Log

**Base path**: `/api/v1/kbs/{kb_id}/candidate-audit-logs`  
**Version**: 1.0.0 (Epic 4)

---

## GET /candidate-audit-logs

查询候选确认相关操作日志。

**Query**:

| Param | Notes |
|-------|-------|
| candidate_id | doc_/tpl_ 复合 ID |
| import_id | 关联导入批次 |
| batch_id | 批量操作 ID |
| action | edit, publish, publish_failed, ignore, merge, split, batch_confirm, batch_reject |
| operator_id | 可选 |
| from, to | ISO8601 时间范围 |
| page, page_size | 默认 page_size=20 |

**Response `data`**:

```json
{
  "items": [
    {
      "audit_id": "uuid",
      "candidate_id": "doc_uuid",
      "batch_id": null,
      "action": "publish",
      "operator_id": "admin",
      "trace_id": "uuid",
      "detail": {
        "confirm_as": "ku",
        "confirmed_object_id": "uuid",
        "review_comment": "已核对"
      },
      "created_at": "2026-06-14T10:02:00Z"
    },
    {
      "audit_id": "uuid",
      "candidate_id": "doc_uuid",
      "batch_id": "uuid",
      "action": "publish_failed",
      "operator_id": "admin",
      "trace_id": "uuid",
      "detail": {
        "error_code": "PUBLISH_VALIDATION_FAILED",
        "message": "missing knowledge_type"
      },
      "created_at": "2026-06-14T10:01:30Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```

---

## GET /candidate-audit-logs/{audit_id}

单条审计详情（大 payload merge/split 时 detail 可能含 merged_ids[]）。

**Response `data`**: 同上 items[0] 形状。

---

## Errors

| Code | HTTP | When |
|------|------|------|
| AUDIT_LOG_NOT_FOUND | 404 | |

---

## Notes

- 与 Epic 3 `actual_bid_audit_logs` / Epic 2 `template_audit_logs` **分离**；工作台仅查本 API。
- 所有 confirm/batch/merge/split/edit 写路径 MUST 同步写审计（FR-011）。
