# API Contract: Bid Outline

**Base path**: `/api/v1/kbs/{kb_id}/bid-outlines`  
**Version**: 1.0.0 (Epic 3)

共用约定见 [product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

## Common enums

**outline_status**: `draft` | `confirmed` | `published` | `deprecated`

**outline_node_status**: `draft` | `confirmed` | `deprecated`

**diff_status**: `pending` | `applied` | `rejected`

---

## GET /

Bid Outline 列表（目录中心）。

**Query**: `import_id`, `source_doc_id`, `status`, `q` (outline_name), `page`, `page_size`

**Response `data.items[]`**:

```json
{
  "bid_outline_id": "uuid",
  "source_doc_id": "uuid",
  "import_id": "uuid",
  "outline_name": "某某项目投标目录",
  "outline_type": "actual_bid",
  "status": "draft",
  "extract_strategy": "toc",
  "project_name": "某某项目",
  "customer_name": "某某客户",
  "node_count": 28,
  "needs_manual_review": false,
  "updated_at": "2026-06-12T10:02:00Z"
}
```

---

## GET /{bid_outline_id}

Outline 详情 + 根级节点摘要。

---

## GET /{bid_outline_id}/nodes

完整目录树。

**Response `data`**:

```json
{
  "bid_outline_id": "uuid",
  "status": "draft",
  "structure_locked_at": null,
  "nodes": [
    {
      "outline_node_id": "uuid",
      "parent_id": null,
      "title": "1. 技术方案",
      "level": 1,
      "sort_order": 0,
      "chapter_taxonomy_id": "uuid",
      "source_node_id": "uuid",
      "product_category_ids": [],
      "status": "draft",
      "needs_manual_review": false
    }
  ]
}
```

---

## PATCH /{bid_outline_id}/nodes/{outline_node_id}

编辑单个节点（标题、层级、排序、分类）。

**Body** (partial):

```json
{
  "title": "1. 总体技术方案",
  "parent_id": "uuid",
  "sort_order": 1,
  "chapter_taxonomy_id": "uuid",
  "product_category_ids": ["uuid"]
}
```

**Side effects**: 写 `actual_bid_audit_logs`；**不修改** Document Tree。

---

## POST /{bid_outline_id}/nodes/batch

批量操作：合并、删除、重排序。

**Body**:

```json
{
  "operations": [
    { "op": "delete", "outline_node_id": "uuid" },
    { "op": "merge", "source_node_ids": ["uuid", "uuid"], "target_title": "资质证明" },
    { "op": "reorder", "parent_id": "uuid", "ordered_node_ids": ["uuid", "uuid"] }
  ]
}
```

**Response `data`**: 更新后树摘要 + `audit_id`。

---

## POST /{bid_outline_id}/confirm

确认目录结构（写入 `structure_locked_at`）；之后重解析仅产生 diff。

**Body**:

```json
{
  "status": "confirmed"
}
```

---

## GET /{bid_outline_id}/diffs

列出重解析产生的结构差异。

**Response `data.items[]`**:

```json
{
  "diff_id": "uuid",
  "parse_task_id": "uuid",
  "status": "pending",
  "diff_payload": {
    "added": [{ "title": "2.3 安全方案", "level": 2 }],
    "removed": [{ "outline_node_id": "uuid", "title": "旧章节" }],
    "renamed": [{ "outline_node_id": "uuid", "from": "方案", "to": "技术方案" }],
    "moved": [{ "outline_node_id": "uuid", "from_parent": "uuid", "to_parent": "uuid" }]
  },
  "created_at": "2026-06-12T11:00:00Z"
}
```

---

## POST /{bid_outline_id}/diffs/{diff_id}/apply

人工应用差异（选择性合并）。

**Body**:

```json
{
  "accept_added": true,
  "accept_removed_ids": ["uuid"],
  "accept_renamed_ids": ["uuid"],
  "accept_moved_ids": ["uuid"]
}
```

**Response `data`**: 更新后 `nodes` 树。

---

## POST /{bid_outline_id}/diffs/{diff_id}/reject

拒绝差异，保持当前锁定结构。

---

## Errors

| Code | HTTP | When |
|------|------|------|
| OUTLINE_NOT_FOUND | 404 | |
| OUTLINE_LOCKED_CONFLICT | 409 | 非法编辑已 deprecated 目录 |
| INVALID_TREE_OPERATION | 400 | 合并/移动导致环或孤儿节点 |
| DIFF_NOT_PENDING | 409 | diff 已处理 |
