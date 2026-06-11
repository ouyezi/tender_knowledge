# API Contract: File Import

**Base path**: `/api/v1/kbs/{kb_id}/file-imports`  
**Version**: 1.0.0 (Epic 1)

共用 envelope、错误码、`X-Operator-Id`、`X-Trace-Id` 约定见
[product-category-api.md](../../001-classification-base/contracts/product-category-api.md)。

## Common enums

**file_type**: `docx` | `pdf` | `ppt` | `xlsx` | `image` | `other`

**file_purpose**: `actual_bid` | `template_file` | `qualification` | `ppt_material` |
`cover_guide` | `writing_guide` | `wiki_source` | `other`

**status**: `uploaded` | `need_confirm` | `confirmed` | `processing` | `completed` |
`failed` | `ignored`

**target_object_type**: `document` | `template_material` | `manual_asset` | `wiki` | `ignored`

---

## POST /

上传单个文件并创建 File Import。

**Content-Type**: `multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| file | binary | yes | 单文件 |
| duplicate_action | string | no | `normal`（默认）\| `skip` \| `new_version` |
| parent_import_id | uuid | no | `new_version` 时可选，指向版本链 |

**Flow**:

1. 校验格式/大小（见 research R7）。
2. 流式写入存储，创建 `FileImport`（`status=uploaded`）。
3. 若 hash 已存在且 `duplicate_action=normal` → `409 DUPLICATE_FILE`（见下）。
4. 触发后台 hash + 建议任务。
5. 返回 `import_id`（不等待建议完成）。

**Response `data`** (201):

```json
{
  "import_id": "uuid",
  "kb_id": "uuid",
  "file_name": "餐补模板.docx",
  "file_type": "docx",
  "file_size": 102400,
  "status": "uploaded",
  "version_no": 1,
  "created_at": "2026-06-11T10:00:00Z"
}
```

**409 DUPLICATE_FILE**:

```json
{
  "error": {
    "code": "DUPLICATE_FILE",
    "message": "相同内容的文件已导入",
    "details": {
      "existing_import_ids": ["uuid"],
      "file_hash": "sha256hex"
    }
  },
  "trace_id": "uuid"
}
```

客户端可带 `duplicate_action=skip`（返回已有记录）或 `new_version`（创建新版本链）。

---

## GET /

分页列出 File Import。

**Query**:

| Param | Type | Default |
|-------|------|---------|
| status | string | — |
| file_purpose | string | — |
| q | string | 文件名模糊搜索 |
| page | int | 1 |
| page_size | int | 20 |

**Response `data`**:

```json
{
  "items": [
    {
      "import_id": "uuid",
      "file_name": "餐补模板.docx",
      "file_type": "docx",
      "file_size": 102400,
      "file_hash": "sha256hex",
      "file_purpose": null,
      "status": "need_confirm",
      "version_no": 1,
      "created_at": "2026-06-11T10:00:00Z",
      "updated_at": "2026-06-11T10:00:05Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

---

## GET /{import_id}

查询单条导入详情（含建议，若已生成）。

**Response `data`**:

```json
{
  "import_id": "uuid",
  "kb_id": "uuid",
  "file_name": "餐补模板.docx",
  "file_type": "docx",
  "file_size": 102400,
  "file_hash": "sha256hex",
  "hash_status": "computed",
  "storage_path": "kb-id/import-id/餐补模板.docx",
  "file_purpose": null,
  "product_category_ids": [],
  "chapter_taxonomy_id": null,
  "target_object_type": null,
  "enter_parsing": true,
  "status": "need_confirm",
  "parent_import_id": null,
  "version_no": 1,
  "version": 2,
  "suggestion": {
    "suggested_purpose": "template_file",
    "purpose_confidence": 0.85,
    "suggested_product_category_ids": ["uuid"],
    "suggested_chapter_taxonomy_id": "uuid",
    "suggestion_source": "rule",
    "rationale": "文件名含「模板」且扩展名为 docx"
  },
  "created_by": "admin",
  "created_at": "2026-06-11T10:00:00Z",
  "updated_at": "2026-06-11T10:00:05Z"
}
```

`suggestion` 在 `status=uploaded` 且后台未完成时为 `null`。

---

## GET /{import_id}/tasks

查询与该导入关联的任务（`file_import`、`file_purpose_classify`）。

**Response `data`**:

```json
{
  "items": [
    {
      "task_id": "uuid",
      "task_type": "file_import",
      "status": "completed",
      "retry_count": 0,
      "log_lines": [
        { "ts": "2026-06-11T10:00:01Z", "level": "info", "message": "文件已落盘" }
      ],
      "started_at": "2026-06-11T10:00:00Z",
      "finished_at": "2026-06-11T10:00:02Z"
    }
  ]
}
```

---

## POST /{import_id}/retry

重新处理失败或未完成的导入后台任务（hash/建议/路由）。

**Body** (optional):

```json
{
  "scope": "all | classify | route"
}
```

**Preconditions**: `status` ∈ `failed`, `uploaded`（超时）, 或 `confirmed` 且下游创建失败。

**Response `data`**: `{ "import_id", "status", "tasks_enqueued": ["file_purpose_classify"] }`

---

## GET /{import_id}/downstream-entries

查询用途确认后创建的下游任务占位（供 Epic 2/3 集成验收）。

**Response `data`**:

```json
{
  "items": [
    {
      "entry_id": "uuid",
      "task_type": "template_file_parse",
      "status": "pending",
      "created_at": "2026-06-11T10:05:00Z"
    }
  ]
}
```
