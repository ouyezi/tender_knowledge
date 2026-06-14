# Design: 来源导入删除 500 修复与已发布资产保护

**Date**: 2026-06-14  
**Status**: Approved  
**Scope**: File Import 删除链路、purge 服务补全、已发布资产级联废弃、前端删除 UX

## Background

用户在「来源导入中心」删除导入记录时，浏览器控制台报错：

```
DELETE /api/v1/kbs/{kb_id}/file-imports/{import_id} → 500 Internal Server Error
```

同时存在 antd 弃用警告：`Modal destroyOnClose` 应改为 `destroyOnHidden`（次要，非 500 根因）。

## Root Cause Analysis

| 现象 | 根因 |
|------|------|
| DELETE 500 | `file_import_purge_service.py` 级联清理不完整；未处理 `knowledge_units`、`wikis`、`manual_assets` 等对 `file_imports.import_id` 的 NOT NULL 外键；删除顺序未考虑 `document_media_assets`；未捕获 `IntegrityError` 导致裸 500 |
| 与 Epic 1 冲突 | Epic 1 规定「已发布对象不允许物理删除，只能走废弃流程」；当前 UI 文案暗示硬删除全部下游数据 |
| antd 警告 | 多个 Modal/Drawer 仍使用 `destroyOnClose` |

**purge 服务当前缺口（相对 `file_imports.import_id` FK）**

| 已处理 | 未处理 / 顺序问题 |
|--------|-------------------|
| candidate_knowledges, documents, bid_outlines, templates, import_tasks 等 | `knowledge_units`, `wikis`, `manual_assets`（已发布资产） |
| | `document_media_assets`（须在 documents 之前删） |
| | `retrieval_index_entries`（废弃/清理检索索引） |
| | 物理 `DELETE file_imports` 行（与保留已废弃资产 FK 冲突） |

## Product Decisions (Approved)

1. **存在已发布 KU / Wiki / Manual Asset 时**：默认阻止删除，返回 409；用户二次确认后可**级联废弃**（非物理删除）。
2. **墓碑记录**：`file_imports` 行保留并标记 `status=deleted`，从列表隐藏；已废弃资产保留 `import_id` 以维持溯源。
3. **无已发布资产时**：单次确认后直接墓碑化 + 清理中间数据。
4. **API 方案**：扩展现有 DELETE + 新增 purge-impact 预览（方案 1）。

## Goals

- 删除导入记录不再 500；行为可预期、可测试
- 已发布知识资产受保护；确认后级联废弃并同步检索索引
- 列表不再展示已删除导入；audit log 仍可追溯
- 前端删除流程清晰展示影响范围
- 顺带修复 antd `destroyOnClose` 弃用警告

## Non-Goals

- 已发布资产的物理删除
- 已删除导入的「恢复」功能
- 重构整个 purge 为 DB 级 `ON DELETE CASCADE`
- 修改 `import_id` 为可空（墓碑方案已满足 FK）

## Architecture

### 1. FileImport 墓碑状态

在 `FileImportStatus` 枚举新增 `deleted`：

- 墓碑行保留 `import_id`，满足 KU / Wiki / Manual Asset 外键
- `list_file_imports` 默认过滤 `status != deleted`
- 软删除时：删除 storage 目录、物理清理解析中间数据、更新 `status=deleted`、`updated_at`

PostgreSQL enum 同步：在 `init_db.py` 增加 `fileimportstatus` 的 `_sync_postgres_enum`（与现有模式一致）；SQLite 测试由 `create_all` 重建 enum。

### 2. 删除影响矩阵

| 对象 | 无已发布资产 | 有已发布 + `deprecate_published=true` |
|------|-------------|--------------------------------------|
| 已发布 KU / Wiki / Manual Asset | — | **废弃**（`status=deprecated`, `deprecated_at=now()`） |
| 检索索引 | 按 import / object 清理或 deprecate | 对已发布资产调用 `IndexBuilder.deprecate_entry` |
| 候选知识、文档、大纲、模板中间态、任务等 | 物理删除 | 物理删除 |
| storage 文件目录 | 删除 | 删除 |
| `file_imports` 行 | 墓碑化 | 墓碑化 |

### 3. Purge 服务重构

将 `file_import_purge_service.py` 拆为职责清晰的函数：

```text
check_purge_impact(db, kb_id, import_id) -> PurgeImpactReport
deprecate_published_assets(db, kb_id, import_id, operator_id) -> DeprecateSummary
soft_purge_import(db, kb_id, import_id, *, deprecate_published: bool) -> PurgeSummary
```

**`_purge_import_core` 清理顺序（中间数据）**

1. 递归处理 `parent_import_id` 子导入（现有逻辑）
2. 若 `deprecate_published`：废弃 KU / Wiki / Manual Asset + 检索索引 deprecate
3. `document_media_assets`（按 document_id）
4. `candidate_knowledges`, `candidate_knowledge_stubs`
5. `_purge_actual_bid_for_import`（documents, outlines, parse tasks…）
6. `_purge_template_for_import`
7. `template_materials`, `downstream_task_entries`, `import_tasks`, `file_purpose_suggestions`
8. `classification_references`（file_import 类型）
9. `TemplateLibrary.source_import_id` / `TemplateAuditLog.import_id` 置空（现有逻辑）
10. 删除 storage 目录
11. **更新** `FileImport.status = deleted`（替换现有物理 DELETE）

**错误处理**

- `FileImportPurgeServiceError`：结构化 4xx（现有）
- `sqlalchemy.exc.IntegrityError`：rollback → 409 `PURGE_CONFLICT`
- 已是 `deleted`：幂等返回 200

## API Contract

### GET purge-impact

```
GET /api/v1/kbs/{kb_id}/file-imports/{import_id}/purge-impact
```

Response `data`:

```json
{
  "import_id": "uuid",
  "file_name": "example.docx",
  "has_published_assets": true,
  "published_counts": { "ku": 2, "wiki": 1, "manual_asset": 0 },
  "published_total": 3,
  "intermediate_counts": {
    "candidate_knowledges": 5,
    "documents": 1,
    "import_tasks": 2
  }
}
```

- `published_*`：仅 `status=published` 的 KU / Wiki / Manual Asset
- `intermediate_*`：将被物理清理的中间数据

### DELETE file-import

```
DELETE /api/v1/kbs/{kb_id}/file-imports/{import_id}?deprecate_published=false|true
```

| 场景 | HTTP | error.code |
|------|------|------------|
| 无已发布资产 | 200 | — |
| 有已发布且 `deprecate_published` 非 true | 409 | `PUBLISHED_ASSETS_EXIST` |
| 有已发布且 `deprecate_published=true` | 200 | — |
| 不存在 | 404 | `NOT_FOUND` |
| 已 deleted | 200（幂等） | — |
| FK 冲突 | 409 | `PURGE_CONFLICT` |

409 `error.details` 附带与 purge-impact 相同结构的影响摘要。

200 `data`:

```json
{
  "import_id": "uuid",
  "file_name": "example.docx",
  "status": "deleted",
  "deprecated_counts": { "ku": 2, "wiki": 1, "manual_asset": 0 },
  "deleted_counts": { "documents": 1, "candidate_knowledges": 5, "storage_dirs": 1 }
}
```

### 列表过滤

`GET /file-imports`：`WHERE kb_id = ? AND status != 'deleted'`

## Frontend Changes

### FileImportCenter 删除流程

```text
点击删除
  → GET purge-impact
  → has_published_assets?
       否 → Popconfirm「将删除导入文件及解析数据，不可恢复」→ DELETE（无参数）
       是 → Modal 展示 published_counts + 警告文案
            「将废弃 N 个已发布知识资产，并删除导入文件及解析数据，不可恢复」
            → 确认 → DELETE ?deprecate_published=true
  → 刷新列表 + message.success
```

- 复用 `ImpactAnalysisModal` 展示 `published_counts`（扩展 props 或映射为 `ImpactReport` 形状）
- 409 `PUBLISHED_ASSETS_EXIST`：展示后端 message，不重复弹窗
- `fileImports.ts`：新增 `getFileImportPurgeImpact()`；`deleteFileImport()` 增加可选 `deprecatePublished` 参数

### antd 弃用修复

以下文件 `destroyOnClose` → `destroyOnHidden`：

- `frontend/src/components/ImpactAnalysisModal.tsx`
- `frontend/src/components/MergeWizard.tsx`
- `frontend/src/pages/FileImportCenter/ConfirmDrawer.tsx`
- `frontend/src/pages/FileImportCenter/TaskLogDrawer.tsx`
- `frontend/src/pages/KnowledgeBaseList/index.tsx`
- `frontend/src/pages/OutlineCenter/ParseTaskLogDrawer.tsx`
- `frontend/src/pages/TemplateLibraryCenter/PublishModal.tsx`

## Backend File Touch List

| 文件 | 变更 |
|------|------|
| `backend/src/models/file_import.py` | `FileImportStatus.deleted` |
| `backend/src/db/init_db.py` | sync `fileimportstatus` enum |
| `backend/src/services/file_import_purge_service.py` | 重构 + 补全 + 软删除 |
| `backend/src/api/routes/file_imports.py` | purge-impact 路由、DELETE 参数、列表过滤、IntegrityError |
| `backend/tests/contract/test_file_import_delete.py` | 新建契约测试 |

## Testing Plan

| 用例 | 预期 |
|------|------|
| seed 仅候选数据 → DELETE | 200；中间数据清除；import.status=deleted |
| seed 已发布 KU → DELETE 无 flag | 409；KU 仍 published |
| seed 已发布 KU → DELETE deprecate_published=true | 200；KU deprecated；import deleted |
| 重复 DELETE 已 deleted import | 200 幂等 |
| GET purge-impact 计数 | 与 DB 一致 |
| list_file_imports 不含 deleted | 200 |

## Acceptance Criteria

1. 来源导入中心删除无已发布资产的记录成功，列表不再展示
2. 存在已发布资产时首次 DELETE 返回 409 并展示影响；确认级联废弃后删除成功
3. 已发布 KU/Wiki/Manual Asset 变为 deprecated，检索索引同步 deprecate
4. 不再出现 DELETE file-imports 500（FK 冲突转为 409）
5. 控制台无 `destroyOnClose` 弃用警告（Modal/Drawer 范围内）

## Risks & Mitigations

| 风险 | 缓解 |
|------|------|
| 遗漏新表 FK 至 file_imports | purge-impact 集成测试 + IntegrityError 兜底 409 |
| enum `deleted` 未同步到 PG | init_db `_sync_postgres_enum` + 启动验证 |
| 墓碑 import 占用 hash 唯一索引 | 保留行不影响 hash 唯一约束（同 kb_id+hash 仍唯一）；新上传同文件可走 duplicate 流程 |
