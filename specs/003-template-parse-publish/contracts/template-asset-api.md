# API Contract: Template Assets (Material / Variable / Rule)

**Base path**: `/api/v1/kbs/{kb_id}/templates/{template_id}`  
**Version**: 1.0.0 (Epic 2)

共用约定见 [product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

---

## Template Material

**Sub-path**: `/materials`

### GET /materials

**Query**: `template_chapter_id`, `material_type`, `status`, `page`, `page_size`

### POST /materials

**Body**:

```json
{
  "template_chapter_id": "uuid",
  "material_type": "fixed_paragraph",
  "title": "固定说明段",
  "summary": "",
  "content": "...",
  "import_id": "uuid",
  "storage_path": null,
  "product_category_ids": [],
  "extract_as_candidate": false
}
```

### PATCH /materials/{material_id}

更新元数据、`product_category_ids`、`extract_as_candidate`、`status`。

### POST /materials/{material_id}/deprecate

---

## Template Variable

**Sub-path**: `/variables`

MVP：`value_type` 默认 `string`；占位符 `{{variable_key}}`。

### GET /variables

### POST /variables

**Body**:

```json
{
  "template_chapter_id": "uuid",
  "variable_key": "project_name",
  "display_name": "项目名称",
  "value_type": "string",
  "required": true,
  "default_value": "",
  "description": ""
}
```

**409**: `variable_key` 重复。

### PATCH /variables/{variable_id}

### DELETE /variables/{variable_id}

MVP：设 `status=inactive`，非物理删除。

---

## Template Rule

**Sub-path**: `/rules`

MVP 可写 `rule_type`: `required` | `optional` | `product_match` only。

### GET /rules

### POST /rules

**required** 示例:

```json
{
  "template_chapter_id": "uuid",
  "rule_type": "required",
  "action": "enable",
  "message": "该章节为必选"
}
```

**product_match** 示例:

```json
{
  "template_chapter_id": "uuid",
  "rule_type": "product_match",
  "condition": {
    "field": "product_category",
    "operator": "in",
    "value": ["uuid"]
  },
  "action": "enable",
  "message": "餐补产品下启用"
}
```

**422 VALIDATION**: 提交 `conditional` | `mutex` | `asset_required` 被拒绝。

### PATCH /rules/{rule_id}

### POST /rules/{rule_id}/deprecate

---

## Candidate Knowledge Stub（Epic 4 只读扩展）

**Sub-path**: `/candidate-stubs`

### GET /candidate-stubs

**Query**: `status=pending_confirm`

Epic 2 管理端可查看解析产生的候选；Epic 4 工作台批量认领 `epic4_batch_id`。

### PATCH /candidate-stubs/{stub_id}

Epic 2 允许 `status=rejected`；`confirmed` 留给 Epic 4。

---

## 发布校验聚合

`POST .../templates/{template_id}/publish` 与 library publish 调用内部校验：

| 检查项 | 规则 |
|--------|------|
| 必填章节 | `rule_type=required` 对应章节存在且非 ignored |
| 必填变量 | `required=true` 须有 `default_value` 或文档说明可空 |
| 章节树 | 至少 1 个非 ignored 根节点 |
| 确认状态 | `confirmed=true` |

失败返回 `422 PUBLISH_VALIDATION` + `details[]`。
