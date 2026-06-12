# API Contract: Template Library & Template

**Base paths**:

- `/api/v1/kbs/{kb_id}/template-libraries`
- `/api/v1/kbs/{kb_id}/templates`

**Version**: 1.0.0 (Epic 2)

共用约定见 [product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

## Common enums

**library_type**: `technical` | `commercial` | `qualification` | `product_specific` | `custom`

**template_type**: `technical_bid` | `commercial_bid` | `qualification` | `chapter_set` | `custom`

**status**: `draft` | `reviewing` | `published` | `deprecated`

---

## Template Library

### GET /template-libraries

**Query**: `status`, `q`, `product_category_id`, `page`, `page_size`

**Response `data.items[]`**:

```json
{
  "template_library_id": "uuid",
  "library_name": "餐补技术标模板库",
  "library_type": "technical",
  "product_category_ids": ["uuid"],
  "status": "draft",
  "version": "1.0",
  "template_count": 3,
  "source_import_id": "uuid",
  "updated_at": "2026-06-12T10:00:00Z"
}
```

Epic 5 只读消费：`status=published` 过滤。

### POST /template-libraries

**Body**:

```json
{
  "library_name": "餐补技术标模板库",
  "library_type": "technical",
  "product_category_ids": [],
  "source_import_id": "uuid"
}
```

**Response** (201): 完整 library 对象。

### GET /template-libraries/{template_library_id}

含关联 `templates` 摘要列表。

### PATCH /template-libraries/{template_library_id}

更新 `library_name`, `library_type`, `product_category_ids`, `owner` 等；不可改 `kb_id`。

### POST /template-libraries/{template_library_id}/publish

发布校验：

- 库内所有非 ignored Template 已 `confirmed=true`
- required 规则与必填变量校验通过

**Body** (optional):

```json
{
  "cascade_templates": true,
  "version_note": "首次发布"
}
```

**Response**:

```json
{
  "template_library_id": "uuid",
  "status": "published",
  "version": "1.0",
  "version_no": 1,
  "snapshot_id": "uuid",
  "published_at": "2026-06-12T11:00:00Z"
}
```

### POST /template-libraries/{template_library_id}/deprecate

软废弃；不可物理删除。

### GET /template-libraries/{template_library_id}/snapshots

历史发布快照列表。

### GET /template-libraries/{template_library_id}/snapshots/{snapshot_id}

只读快照 JSON。

---

## Template

### GET /templates

**Query**: `template_library_id`（`uncategorized=true` 查未归类）, `status`, `import_id`, `q`, `page`, `page_size`

### GET /templates/{template_id}

**Response `data`**:

```json
{
  "template_id": "uuid",
  "template_library_id": null,
  "source_import_id": "uuid",
  "template_name": "餐补模板.docx",
  "template_type": "technical_bid",
  "product_category_ids": [],
  "status": "draft",
  "confirmed": true,
  "structure_locked_at": "2026-06-12T10:05:00Z",
  "version": "1.0",
  "chapter_count": 12,
  "material_count": 5
}
```

### PATCH /templates/{template_id}

更新 `template_name`, `template_type`, `product_category_ids`, `template_library_id`（归类/移库）。

### POST /templates/{template_id}/publish

单 Template 发布（未归类模板可独立发布；不参与 library 级推荐 unless 后续归入 published library）。

**Response**: 同 library publish 结构。

### POST /templates/{template_id}/deprecate

### GET /templates/{template_id}/snapshots

历史版本。

---

## 未归类模板

- `template_library_id=null` 表示未归类。
- `GET /templates?uncategorized=true` 列出未归类 draft/published Template。
- 移入库：`PATCH /templates/{id}` 设置 `template_library_id`。
