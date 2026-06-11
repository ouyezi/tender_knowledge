# API Contract: Knowledge Base

**Base path**: `/api/v1/kbs`  
**Version**: 1.0.0 (Epic 0 P0)

共用 envelope、错误码、`X-Operator-Id` 约定见 [product-category-api.md](./product-category-api.md)。

## GET /

列出知识库。

**Query**: `status` — `active`（默认）| `inactive`

**Response `data`**:

```json
{
  "items": [
    {
      "kb_id": "uuid",
      "name": "标书知识库-demo",
      "status": "active"
    }
  ]
}
```

---

## POST /

创建知识库；可选从已有 KB 深拷贝分类树。

**Body**:

```json
{
  "name": "KB-cloned",
  "clone_from_kb_id": "uuid-or-null"
}
```

**Clone 行为**: 复制源 KB 的 Product Category 树（含别名）、Chapter Taxonomy 树（含同义名与产品绑定），并写入 `kb_clone_logs`。

**Response `data`**: `{ "kb_id", "name", "status" }`

---

## GET /{kb_id}

知识库详情。

---

## PATCH /{kb_id}

更新名称。

**Body**: `{ "name": "新名称" }`

---

## POST /{kb_id}/deactivate

停用知识库。停用后该 KB 下写操作受 `kb_write_guard` 拦截（403 KB_READ_ONLY）；读操作仍可用。

**Response `data`**: `{ "kb_id", "name", "status": "inactive" }`

---

## 嵌套资源

| 路径 | 说明 |
|------|------|
| `/api/v1/kbs/{kb_id}/product-categories/*` | 产品分类 — 见 product-category-api.md |
| `/api/v1/kbs/{kb_id}/chapter-taxonomies/*` | 章节分类 — 见 chapter-taxonomy-api.md |
