# API Contract: Chapter Taxonomy

**Base path**: `/api/v1/kbs/{kb_id}/chapter-taxonomies`  
**Version**: 1.0.0 (Epic 0)

共用 envelope、错误码、`X-Operator-Id` 约定见 [product-category-api.md](./product-category-api.md)。

---

## GET /tree

章节分类树。结构与 Product Category tree 对称，字段映射：

| Product Category | Chapter Taxonomy |
|------------------|------------------|
| category_id | taxonomy_id |
| category_name | standard_name |
| category_code | taxonomy_code |
| aliases | synonyms（嵌套或独立字段） |

---

## GET /{taxonomy_id}

详情含：同义名列表、绑定的 `product_category_ids`、breadcrumb、子节点。

---

## POST /

**Body**:

```json
{
  "parent_id": null,
  "standard_name": "售后服务方案",
  "taxonomy_code": "after-sales",
  "description": "",
  "synonyms": ["驻场服务方案", "服务保障方案"],
  "product_category_ids": []
}
```

---

## PATCH /{taxonomy_id}

更新标准名、描述、状态。

---

## PUT /{taxonomy_id}/synonyms

替换同义名全集。

---

## PUT /{taxonomy_id}/product-categories

维护与 Product Category 的 M:N 绑定。

**Body**: `{ "product_category_ids": ["uuid", "uuid"], "source": "manual" }`

**Query filter support**: `GET /?product_category_id={uuid}` 返回绑定的章节类型列表。

---

## GET /{taxonomy_id}/impact

同 Product Category impact 结构；`classification_type=chapter_taxonomy`。

---

## POST /{taxonomy_id}/deactivate | /archive | /merge

语义与 Product Category 一致。

---

## GET /search

按标准名或同义名搜索。

**Query**: `q`, `product_category_id`（可选过滤）, `status=active`

---

## Epic 2/3 预留（Epic 0 不实现）

- `POST /discover-candidates` — 从 Bid Outline / Template Chapter 批量建议新 taxonomy（FR-013  defer）。
