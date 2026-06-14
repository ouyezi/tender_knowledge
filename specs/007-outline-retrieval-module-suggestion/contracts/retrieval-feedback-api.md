# API Contract: Retrieval Feedback

**Base path**: `/api/v1/kbs/{kb_id}/retrieval/feedback`  
**Version**: 1.0.0 (Epic 5)

---

## POST /

提交检索或模块建议反馈。

**Body**:

```json
{
  "trace_id": "uuid",
  "feedback_type": "useful",
  "object_type": "ku",
  "object_id": "uuid",
  "rank_position": 1,
  "expected_object_ids": [],
  "comment": "正是需要的架构描述",
  "filter_adjustment": {
    "product_category_ids": ["uuid"],
    "chapter_taxonomy_ids": ["uuid"],
    "knowledge_types": ["solution"]
  }
}
```

**feedback_type** 枚举：

```text
click | adopt | copy | add_to_draft | useful | not_useful | false_positive | false_negative
```

漏召回（`false_negative`）时 `expected_object_ids` 或 `comment` 至少一项非空。

**Response `data`**:

```json
{
  "feedback_id": "uuid",
  "trace_id": "uuid",
  "feedback_type": "useful",
  "created_at": "2026-06-14T10:05:00Z"
}
```

**Errors**:

| Code | HTTP | When |
|------|------|------|
| TRACE_NOT_FOUND | 404 | trace_id 不存在 |
| INVALID_FEEDBACK_TYPE | 422 | 枚举无效 |
| FALSE_NEGATIVE_MISSING_EXPECTATION | 422 | 漏召回未提供期望结果 |

---

## GET /

反馈列表（检索优化中心）。

**Query**: `trace_id`, `feedback_type`, `from`, `to`, `page`, `page_size`

---

## POST /{feedback_id}/promote-to-eval-case

将反馈晋升为评测用例（待人工确认状态）。

**Body**:

```json
{
  "eval_set_id": "uuid",
  "expected_object_ids": ["uuid"],
  "negative_object_ids": []
}
```

**Response `data`**: `{ "eval_case_id": "uuid", "status": "pending" }`
