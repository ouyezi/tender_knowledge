# API Contract: Candidate Knowledge Confirm & Edit

**Base path**: `/api/v1/kbs/{kb_id}/candidates`  
**Version**: 1.0.0 (Epic 4)

共用约定见 [product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

**Candidate ID 约定**：`doc_{uuid}`（document 通道）或 `tpl_{uuid}`（template stub 通道），
与 Epic 3 只读 API 一致。

---

## PATCH /candidates/{candidate_id}

编辑待确认候选（仅 `status=pending` / stub `pending_confirm`）。

**Body**（部分更新）:

```json
{
  "title": "云平台架构设计（修订）",
  "summary": "...",
  "content": "...",
  "suggested_knowledge_type": "solution",
  "suggested_chapter_taxonomy_id": "uuid",
  "suggested_product_category_ids": ["uuid"],
  "candidate_type": "ku"
}
```

**Response `data`**:

```json
{
  "candidate_id": "doc_uuid",
  "status": "pending",
  "updated_at": "2026-06-14T10:00:00Z"
}
```

**Errors**:

| Code | HTTP | When |
|------|------|------|
| CANDIDATE_NOT_FOUND | 404 | |
| CANDIDATE_NOT_EDITABLE | 409 | 已发布/已忽略/已合并 |
| INVALID_TAXONOMY | 422 | 章节类型不存在或 inactive |
| INVALID_PRODUCT_CATEGORY | 422 | 产品分类无效 |

---

## POST /candidates/{candidate_id}/confirm

单条确认/发布/忽略（核心端点）。

**Body**:

```json
{
  "confirm_as": "ku",
  "title": "云平台架构设计",
  "summary": "...",
  "content": "...",
  "product_category_ids": ["uuid"],
  "chapter_taxonomy_id": "uuid",
  "knowledge_type": "solution",
  "wiki_type": null,
  "asset_type": null,
  "searchable": true,
  "usage_hint": "技术方案章节引用",
  "review_comment": "已核对来源节点",
  "template_id": null,
  "parent_chapter_id": null,
  "category_code": null
}
```

`confirm_as` 枚举：

```text
ku | wiki | template_chapter | manual_asset | chapter_pattern | product_category | ignore
```

**Response `data`**（发布成功）:

```json
{
  "candidate_id": "doc_uuid",
  "confirmed_object_type": "ku",
  "confirmed_object_id": "uuid",
  "status": "published",
  "trace_id": "uuid",
  "idempotent": false
}
```

**Response `data`**（忽略）:

```json
{
  "candidate_id": "doc_uuid",
  "confirmed_object_type": "ignore",
  "confirmed_object_id": null,
  "status": "rejected",
  "trace_id": "uuid"
}
```

**幂等**：若候选已 `published` 且请求 `confirm_as` 与既有对象一致 → `200`，
`idempotent: true`，返回既有 `confirmed_object_id`。

**Errors**:

| Code | HTTP | When |
|------|------|------|
| CANDIDATE_NOT_FOUND | 404 | |
| PUBLISH_VALIDATION_FAILED | 422 | 字段/来源链/分类校验失败 |
| PUBLISH_CONFLICT | 409 | 已发布但 confirm_as 不一致 |
| PUBLISH_IN_PROGRESS | 409 | 并发发布锁 |
| DEPRECATED_TAXONOMY | 422 | 章节类型已废弃 |

---

## POST /candidates/{candidate_id}/retry-publish

发布失败后重试（等价于 confirm，但 MUST 检查 `last_publish_error` 或 partial state）。

**Body**: 同 confirm（可省略字段，沿用候选当前值）。

**Response**: 同 confirm。

---

## POST /candidates/merge

合并多条 pending 候选。

**Body**:

```json
{
  "target_candidate_id": "doc_uuid",
  "source_candidate_ids": ["doc_uuid2", "tpl_uuid3"],
  "title": "合并后标题",
  "summary": "...",
  "content": "...",
  "review_comment": "重复段落合并"
}
```

**Response `data`**:

```json
{
  "target_candidate_id": "doc_uuid",
  "merged_count": 2,
  "status": "pending",
  "trace_id": "uuid"
}
```

**Errors**: `MERGE_INVALID_TARGET` 409, `MERGE_SOURCE_NOT_PENDING` 409

---

## POST /candidates/{candidate_id}/split

拆分单条 pending 候选。

**Body**:

```json
{
  "splits": [
    {
      "title": "片段 A",
      "summary": "...",
      "content": "...",
      "candidate_type": "ku",
      "suggested_chapter_taxonomy_id": "uuid",
      "suggested_product_category_ids": []
    },
    {
      "title": "片段 B",
      "summary": "...",
      "content": "...",
      "candidate_type": "wiki"
    }
  ],
  "review_comment": "按章节类型拆分"
}
```

**Response `data`**:

```json
{
  "source_candidate_id": "doc_uuid",
  "new_candidate_ids": ["doc_new1", "doc_new2"],
  "source_status": "merged",
  "trace_id": "uuid"
}
```

---

## GET /candidates — 扩展查询（Epic 4）

在 Epic 3 参数基础上新增：

| Param | Notes |
|-------|-------|
| chapter_taxonomy_id | 建议章节类型 |
| product_category_id | suggested_product_category_ids 包含 |
| status | pending, published, rejected, merged, all |
| confidence_min | 可选 |

响应形状不变。

---

## Retrieval isolation

- 本 Epic 写 API 创建的正式对象（KU/Wiki/…）才参与 Epic 5 检索索引。
- `GET /candidates` 仍为管理台专用；Epic 5 retrieval API MUST NOT 返回 pending 候选。

---

## Audit

所有写操作 MUST 写 `candidate_confirm_audit_logs`（见 [candidate-audit-api.md](./candidate-audit-api.md)）。
