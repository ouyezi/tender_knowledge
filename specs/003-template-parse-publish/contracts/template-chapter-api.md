# API Contract: Template Chapter

**Base path**: `/api/v1/kbs/{kb_id}/templates/{template_id}/chapters`  
**Version**: 1.0.0 (Epic 2)

共用约定见 [product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

## GET /tree

返回完整章节树（嵌套或 flat 可选）。

**Query**:

| Param | Default | Notes |
|-------|---------|-------|
| format | nested | `nested` \| `flat` |
| include_ignored | false | 是否含 ignored 节点 |
| status | — | 过滤 draft/published |

**Response `data` (nested)**:

```json
{
  "template_id": "uuid",
  "roots": [
    {
      "template_chapter_id": "uuid",
      "title": "1. 项目概述",
      "level": 1,
      "sort_order": 0,
      "parent_id": null,
      "chapter_taxonomy_id": "uuid",
      "product_category_ids": [],
      "required": true,
      "is_fixed_section": true,
      "ignored": false,
      "status": "draft",
      "bound_material_ids": ["uuid"],
      "variable_ids": [],
      "rule_ids": [],
      "children": []
    }
  ]
}
```

Epic 5 只读：`GET ...?status=published` 且 Template/Library 已发布。

---

## POST /

创建章节节点（手工补节点）。

**Body**:

```json
{
  "parent_id": "uuid",
  "title": "新增章节",
  "level": 2,
  "sort_order": 0,
  "chapter_taxonomy_id": "uuid",
  "product_category_ids": [],
  "required": false,
  "is_fixed_section": false
}
```

**Response** (201): 章节对象。

---

## PATCH /{template_chapter_id}

更新单节点字段：`title`, `chapter_taxonomy_id`, `product_category_ids`, `required`,
`is_fixed_section`, `ignored`, `expected_knowledge_types`。

---

## POST /reorder

同级排序。

**Body**:

```json
{
  "parent_id": "uuid",
  "ordered_chapter_ids": ["uuid", "uuid"]
}
```

---

## POST /move

移动节点（含子树）。

**Body**:

```json
{
  "template_chapter_id": "uuid",
  "new_parent_id": "uuid",
  "new_sort_order": 0
}
```

服务端 MUST 校验 level 一致性并级联更新子孙 level。

---

## DELETE /{template_chapter_id}

MVP：**软删除** → 设置 `ignored=true` 或 `status=deprecated`；禁止物理 DELETE。

---

## POST /batch-update

批量保存树编辑（模板库中心一次性提交）。

**Body**:

```json
{
  "expected_template_updated_at": "2026-06-12T10:00:00Z",
  "chapters": [
    {
      "template_chapter_id": "uuid",
      "parent_id": null,
      "title": "1. 项目概述",
      "level": 1,
      "sort_order": 0,
      "chapter_taxonomy_id": "uuid",
      "product_category_ids": [],
      "required": true,
      "is_fixed_section": true,
      "ignored": false
    }
  ]
}
```

**409 CONFLICT**: 模板已被并发修改。

**Response**: 更新后 `tree` + `audit_id`。

---

## GET /{template_chapter_id}

单节点详情，含 bound materials/variables/rules 摘要。
