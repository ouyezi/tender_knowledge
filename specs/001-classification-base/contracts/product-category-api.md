# API Contract: Product Category

**Base path**: `/api/v1/kbs/{kb_id}/product-categories`  
**Version**: 1.0.0 (Epic 0)

## Common

- **Auth**: V3.0 暂缓 RBAC；请求头 `X-Operator-Id` 标识操作者（审计用）。
- **Response envelope**:

```json
{
  "data": {},
  "trace_id": "uuid"
}
```

- **Error envelope**:

```json
{
  "error": {
    "code": "CONFLICT | VALIDATION | NOT_FOUND | INVALID_STATE",
    "message": "human readable",
    "details": {}
  },
  "trace_id": "uuid"
}
```

---

## GET /tree

查询产品分类树（默认仅 `active`；`include_inactive=true` 含停用）。

**Query**: `status`, `include_inactive`, `root_id`（可选，子树）

**Response `data`**:

```json
{
  "nodes": [
    {
      "category_id": "uuid",
      "parent_id": null,
      "category_name": "福利产品",
      "category_code": "welfare",
      "aliases": ["员工福利"],
      "description": "",
      "status": "active",
      "depth": 0,
      "children": []
    }
  ]
}
```

---

## GET /{category_id}

分类详情：父路径 breadcrumb、直接子节点 ID 列表、别名、时间戳。

---

## POST /

创建分类。

**Body**:

```json
{
  "parent_id": null,
  "category_name": "餐补",
  "category_code": "meal",
  "description": "",
  "aliases": ["员工餐补"]
}
```

**Validation**: sibling code 唯一；别名不冲突；parent 须 active。

---

## PATCH /{category_id}

更新 `category_name`, `description`, `status`（非 merge 流）。

---

## PUT /{category_id}/aliases

替换别名全集（服务端校验 normalized 唯一）。

**Body**: `{ "aliases": ["员工餐补", "餐饮福利"] }`

---

## GET /{category_id}/impact

影响分析报告（FR-006, SC-003）。

**Response `data`**: 见 `data-model.md` Classification Impact Report。

---

## POST /{category_id}/deactivate

停用。若存在 active 子节点 → `409 INVALID_STATE`。

---

## POST /{category_id}/archive

归档。默认可选列表排除 archived/merged。

---

## POST /{category_id}/merge

**Body**: `{ "target_category_id": "uuid" }`

**Rules**:

- source ≠ target
- 无父子关系
- 事务：迁移 references、更新 source.status=merged、merged_into_id=target

**Response**: `{ "source_id", "target_id", "migrated_reference_count" }`

---

## GET /search

按名称或别名模糊/精确搜索（Epic 1 消费）。

**Query**: `q`, `limit`, `status=active`

**Response**: `{ "items": [ { "category_id", "category_name", "matched_alias", "path_labels" } ] }`
