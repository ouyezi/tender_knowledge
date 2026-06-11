# Design: Epic 1 来源导入与文件分类确认

**Date**: 2026-06-11  
**Status**: Approved  
**Feature spec**: `specs/002-source-import-classify/spec.md`  
**Implementation plan (Spec Kit)**: `specs/002-source-import-classify/plan.md`  
**Superpowers plan**: `docs/superpowers/plans/2026-06-11-epic1-source-import-classify.md`

## 1. 背景与目标

Epic 1 建立 V3.0 **单文件导入统一入口**：上传 → File Import → 用途/分类建议 → 人工确认 →
按 `file_purpose` 分流至下游任务占位。不负责模板解析、标书目录抽取或候选知识工作台（Epic 2/3/4）。

本设计在 Spec Kit 制品基础上，补充 brainstorming 决议的 **P0–P3 切片、UI 交互、LLM 降级策略、
去重弹窗、与 Epic 0/2/3 集成边界**。

## 2. 设计决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 建议引擎 | **规则为主**；配置 `LLM_API_KEY` 时启用文本摘要 + LLM；未配置或失败时降级为纯规则 |
| D2 | 确认 UI | **列表 + 右侧 Drawer**；上传区在列表页顶部 |
| D3 | 交付切片 | **P0 基建 → P1 上传 → P2 确认 → P3 分流/去重/LLM** |
| D4 | 异步模型 | **FastAPI BackgroundTasks** + `import_tasks` 表；失败可 `retry` |
| D5 | 重复文件 | 上传 409 + Modal：**跳过** / **作为新版本**（`duplicate_action`） |
| D6 | 并发确认 | `expected_version` 乐观锁；不匹配返回 409 CONFLICT |
| D7 | 任务日志 | 导入详情内 **TaskLogDrawer**；本 Epic 不做全局任务中心页 |
| D8 | 导航 | AppShell 增加「来源导入」；依赖 KBContext 已选 kb_id |
| D9 | inactive KB | 与 Epic 0 一致：只读，禁止上传/确认 |
| D10 | 存储 | 本地 `STORAGE_ROOT` + Docker `upload_data` volume；路径 `{kb_id}/{import_id}/{file_name}` |

## 3. 架构与交付切片

### 3.1 交付顺序

```text
P0  导入基础设施（表、存储卷、审计、路由壳、空列表页）
  → P1  上传 + hash + 规则建议 + 列表/上传 UI
  → P2  确认/忽略 API + 确认抽屉 + Epic 0 分类选择器
  → P3  去重/新版本、下游占位、重试、任务日志、可选 LLM
```

### 3.2 P0 — 导入基础设施

| 能力 | 说明 |
|------|------|
| ORM 表 | `file_imports`, `file_purpose_suggestions`, `import_tasks`, `downstream_task_entries`, `import_audit_logs` |
| 存储 | `file_storage` 服务；`STORAGE_ROOT` env；docker-compose `upload_data` |
| 审计 | `import_audit_log`；复用 `AuditMiddleware` trace_id |
| 引用扩展 | `classification_reference.object_type` 增加 `file_import` |
| API 壳 | 注册 `file_imports` router；`GET` 列表返回空 |
| UI 壳 | `/file-imports` 路由 + 导航；空 Table + inactive 只读 Alert |

**P0 验收**：表可创建；inactive KB 上传 403；导航可进入空列表页。

### 3.3 P1 — 单文件上传与建议

- `POST` multipart 上传；流式落盘；`status=uploaded` 后立即返回 `import_id`
- BackgroundTasks：SHA-256 → `file_purpose_suggestions`（规则引擎）→ `status=need_confirm`
- `import_tasks`：`file_import` + `file_purpose_classify`
- UI：`Upload.Dragger` + Table；轮询/刷新至 `need_confirm`

**P1 验收**：5 类文件可上传；5s 内返回 id；典型文件名有规则建议。

### 3.4 P2 — 用途确认

- `POST /confirm`、`POST /ignore`；乐观锁；校验 active 分类
- 写 `classification_reference`（`source=manual|suggested`）
- UI：`ConfirmDrawer`：建议只读区 + 表单（用途、产品分类 TreeSelect、章节类型、是否解析）
- 未确认前 **零** `downstream_task_entries`

**P2 验收**：确认 P95 <1s；忽略不创建下游；版本冲突 409。

### 3.5 P3 — 分流、去重、可恢复

- 确认后按 `file_purpose` 映射创建 `downstream_task_entries`（`pending`）
- 重复：`DUPLICATE_FILE` 409 + `DuplicateFileModal`
- `POST /retry`；`TaskLogDrawer`
- 可选 LLM：`purpose_suggestion` 在 Key 存在时增强；失败保留规则结果

**P3 验收**：`template_file` → `template_file_parse`；`actual_bid` → 三条下游；重复流程通。

### 3.6 明确不在范围

- 模板/标书实际解析、Candidate Knowledge 工作台
- 目录/文件夹批量导入
- 全局任务中心页面
- RBAC、对象存储（S3）首版

## 4. 组件与模块边界

### 4.1 后端（`backend/src/`）

| 模块 | 职责 | 切片 |
|------|------|------|
| `models/file_import.py` 等 | ORM | P0 |
| `services/file_storage.py` | 流式落盘 | P0 |
| `services/file_hash.py` | SHA-256 | P1 |
| `services/purpose_suggestion.py` | 规则 + LLM 门面 | P1, P3 |
| `services/duplicate_detection.py` | hash / name+size | P3 |
| `services/file_import_service.py` | 上传编排 | P1 |
| `services/confirm_service.py` | 确认、忽略、分流 | P2, P3 |
| `services/import_task_runner.py` | BackgroundTasks | P1 |
| `api/routes/file_imports.py` | HTTP | P1–P3 |

### 4.2 前端（`frontend/src/`）

| 模块 | 职责 | 切片 |
|------|------|------|
| `layout/AppShell.tsx` | 导航项「来源导入」 | P0 |
| `pages/FileImportCenter/index.tsx` | 列表 + 上传 | P1 |
| `ConfirmDrawer.tsx` | 用途确认 | P2 |
| `DuplicateFileModal.tsx` | 409 处理 | P3 |
| `TaskLogDrawer.tsx` | 任务日志 | P3 |
| `services/fileImports.ts` | API client | P1–P3 |

### 4.3 依赖原则

- Routes 薄；业务在 services。
- 分类选项 **仅** 来自 Epic 0 读 API。
- 写操作经 `kb_write_guard` + audit。
- Epic 2/3 仅读 `downstream_task_entries`，不在 Epic 1 写 Document/Template 表。

## 5. 数据流

### 5.1 上传 → 建议

```text
POST /api/v1/kbs/{kb_id}/file-imports (multipart)
  → kb_write_guard
  → validate file type/size
  → file_storage.save → storage_path
  → INSERT file_imports (status=uploaded)
  → INSERT import_task (file_import, completed)
  → BackgroundTasks.enqueue(import_task_runner.post_upload):
       hash → UPDATE file_hash / hash_status
       duplicate_detection.hint (非阻塞拒绝，仅标记)
       purpose_suggestion.suggest (rule [→ llm])
       UPSERT file_purpose_suggestions
       UPDATE status=need_confirm
       complete import_task (file_purpose_classify)
  → return { import_id } (201)
```

### 5.2 确认 → 分流

```text
POST .../file-imports/{id}/confirm
  → assert status=need_confirm
  → assert expected_version == file_imports.version
  → validate categories active
  → UPDATE file_imports (confirmed fields, status=confirmed, version++)
  → INSERT classification_reference rows
  → IF enter_parsing: confirm_service.create_downstream_entries(file_purpose)
  → import_audit_log (confirm, route)
```

### 5.3 LLM 降级（D1）

```text
IF not settings.llm_api_key: suggestion_source=rule
ELSE:
  snippet = extract_snippet(file)  # docx/pdf only in MVP
  llm_result = llm_suggest(snippet, filename)
  merge: rule wins when purpose_confidence >= 0.8
  ON llm error: log + keep rule only; task still completed
```

### 5.4 重复文件（D5）

```text
POST upload, hash computed
  → existing import with same (kb_id, file_hash)
  → IF duplicate_action absent: 409 DUPLICATE_FILE + existing_import_ids
  → IF skip: return existing record
  → IF new_version: INSERT with parent_import_id, version_no+1
```

### 5.5 前端确认流

```text
Table row click (need_confirm) → open ConfirmDrawer
  → GET detail + suggestion
  → user edits form
  → POST confirm with expected_version
  → on 409: message + reload detail
  → on success: close drawer, refresh row status
```

## 6. 数据模型补充（相对 data-model.md）

无结构变更；本设计锁定：

- `parent_import_id` + `version_no` 用于新版本链（D5）
- `file_imports.version` 为乐观锁（非业务版本号）
- `downstream_task_entries.task_type` 映射见 `contracts/file-purpose-confirm-api.md`

## 7. API 契约

沿用 `specs/002-source-import-classify/contracts/`：

- `file-import-api.md` — 上传、列表、详情、任务、重试、downstream-entries
- `file-purpose-confirm-api.md` — confirm、ignore、分流表

错误码补充：

| code | 场景 |
|------|------|
| `DUPLICATE_FILE` | hash 重复且未指定 duplicate_action |
| `CONFLICT` | 乐观锁版本不匹配 |
| `INVALID_STATE` | 非 need_confirm 时确认 |
| `KB_READ_ONLY` | inactive KB 写操作 |

## 8. 错误处理

- 统一 envelope + `trace_id`
- 上传失败：不产生不完整 File Import（事务：DB 失败则删除已写文件）
- 确认后下游创建失败：保留 confirmed 状态；`downstream_task_entries` 标 failed；可 retry

## 9. 测试策略

| 切片 | 关键测试 |
|------|----------|
| P0 | 模型 create_all；storage path；inactive KB 403 |
| P1 | multipart 上传；import_id 时效；规则建议（`餐补模板.docx`） |
| P2 | confirm 覆盖建议；ignore 无 downstream；version 409 |
| P3 | DUPLICATE 409；new_version 链；downstream 映射；retry；LLM mock 降级 |

- 后端：`tests/contract/test_file_import_api.py`、`tests/integration/test_upload_confirm_flow.py`
- 前端：ConfirmDrawer 冒烟（可选 Playwright）
- 夹具：`backend/tests/fixtures/sample-template.docx`

## 10. 与 Spec Kit 制品同步项

1. `plan.md` — 已含 P0–P3 与模块映射
2. `quickstart.md` — 随实现更新 VS 场景
3. `specs/002-source-import-classify/tasks.md` — 由 `/speckit-tasks` 或 Superpowers plan 对齐

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| BackgroundTasks 进程重启丢任务 | `import_tasks` 留 pending/failed；`POST /retry` |
| 大文件 hash 慢 | 异步；上传 API 不等待 |
| LLM 延迟/不可用 | 可选；失败降级规则（D1） |
| SQLite 测试与 PG 差异 | 集成测试用 PG 或标记 `@pytest.mark.postgres` |
| 并发确认覆盖 | 乐观锁 + 审计 |

## 12. 审批记录

| 阶段 | 状态 | 日期 |
|------|------|------|
| §1–§9 设计草案 | 已确认 | 2026-06-11 |
| 设计文档书面审阅 | 已确认（用户「确定」） | 2026-06-11 |
| Superpowers 实现计划 | 已生成 | 2026-06-11 |
