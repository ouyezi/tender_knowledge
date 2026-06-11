# API Contract: File Purpose Confirm

**Base path**: `/api/v1/kbs/{kb_id}/file-imports/{import_id}`  
**Version**: 1.0.0 (Epic 1)

确认文件用途、分类与分流目标。共用约定见
[file-import-api.md](./file-import-api.md)。

---

## POST /confirm

保存人工确认结果并触发分流。

**Preconditions**:

- `status` MUST 为 `need_confirm`（或 `failed` 且失败点在确认前，经 retry 恢复）。
- 产品分类与章节类型 MUST 为 active 状态。

**Body**:

```json
{
  "expected_version": 2,
  "file_purpose": "template_file",
  "product_category_ids": ["uuid"],
  "chapter_taxonomy_id": "uuid",
  "enter_parsing": true,
  "target_object_type": "document"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| expected_version | yes | 乐观锁，见 data-model `version` |
| file_purpose | yes* | *忽略流程可用专用 endpoint |
| product_category_ids | no | 可为空数组 |
| chapter_taxonomy_id | no | |
| enter_parsing | no | default true |
| target_object_type | no | 推断自 file_purpose 时可省略 |

**Response `data`** (200):

```json
{
  "import_id": "uuid",
  "status": "confirmed",
  "file_purpose": "template_file",
  "product_category_ids": ["uuid"],
  "chapter_taxonomy_id": "uuid",
  "target_object_type": "document",
  "enter_parsing": true,
  "version": 3,
  "confirmed_by": "admin",
  "confirmed_at": "2026-06-11T10:05:00Z",
  "downstream_entries_created": [
    { "entry_id": "uuid", "task_type": "template_file_parse", "status": "pending" }
  ]
}
```

**Side effects**:

1. 更新 `file_imports` 正式字段。
2. 写入 `classification_reference`（`object_type=file_import`）。
3. 若 `enter_parsing=true` 且非 `other`/忽略，创建 `downstream_task_entries`。
4. 写 `import_audit_log`（action=confirm, route）。

**409 CONFLICT** — `expected_version` 不匹配。

**422 VALIDATION** — 分类已停用或状态不允许确认。

**Performance**: P95 < 1s（SC-005）。

---

## POST /ignore

将文件标记为忽略，不进入解析。

**Body**:

```json
{
  "expected_version": 2,
  "reason": "误上传的临时文件"
}
```

**Response `data`**:

```json
{
  "import_id": "uuid",
  "status": "ignored",
  "target_object_type": "ignored",
  "enter_parsing": false,
  "version": 3
}
```

**Side effects**: 审计日志；**不**创建 `downstream_task_entries`。

---

## 分流映射（normative）

服务端按 `file_purpose` + `enter_parsing` 决定 `downstream_task_entries`：

| file_purpose | enter_parsing=true 时创建的 task_type |
|--------------|--------------------------------------|
| actual_bid | `document_parse`, `bid_outline_extract`, `candidate_knowledge_generate` |
| template_file | `template_file_parse` |
| qualification | `manual_asset_candidate` |
| ppt_material, cover_guide, writing_guide | `template_material_ingest` |
| wiki_source | `wiki_candidate` |
| other | 无（attachment_only） |
| 任意 + enter_parsing=false | 无 |

`target_object_type` 用于审计与 UI 展示，与 task_type 映射在实现层维护。

---

## 与 Epic 0 读接口协作

确认页 MUST 调用既有接口获取选项：

- `GET /api/v1/kbs/{kb_id}/product-categories/tree?status=active`
- `GET /api/v1/kbs/{kb_id}/chapter-taxonomies/tree?status=active`

不得在本 Epic 维护平行分类字典（FR-020）。
