# Research: Epic 1 来源导入与文件分类确认

**Date**: 2026-06-11  
**Feature**: `specs/002-source-import-classify`

## R1 — 文件存储方案

### Decision

采用 **本地文件系统** 作为 MVP 存储后端：`STORAGE_ROOT/{kb_id}/{import_id}/{original_filename}`；
通过环境变量 `STORAGE_ROOT`（默认 `data/uploads`）配置；Docker Compose 增加 named volume
`upload_data` 挂载。

### Rationale

- 仓库已有 PostgreSQL + 单体 FastAPI，无对象存储 SDK 依赖。
- Epic 1 仅需可靠落盘与 `storage_path` 可追溯；生产可后续换 S3/MinIO 适配层。
- 与 constitution「敏感文件加密存储」兼容：MVP 先落盘 + 审计，加密层在 storage adapter 扩展。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 直接存 PostgreSQL BYTEA | 大文件影响 DB 性能与备份体积 |
| MinIO/S3 首版 | 增加本地开发依赖；Epic 1 无多节点分发需求 |
| 仅存 hash 不存文件 | 违反可追溯与 Epic 2/3 解析前置条件 |

---

## R2 — 上传与快速返回流程

### Decision

**两阶段异步模型**：

1. **同步阶段**（上传 API）：校验格式/大小 → 流式写入存储 → 创建 `FileImport`（`status=uploaded`）
   → 创建 `file_import` 任务（`running`→`completed`）→ **立即返回 `import_id`**。
2. **异步阶段**（后台 worker / FastAPI BackgroundTasks）：计算 SHA-256 → 去重检测 →
   运行用途建议 → 更新 `status=need_confirm` → 完成 `file_purpose_classify` 任务。

用途确认 API 为同步写库；确认后同步创建 `DownstreamTaskEntry` 并投递占位任务（Epic 2/3 消费）。

### Rationale

- 满足 SC-002「5 秒内返回 import_id」与 FR-004。
- hash 与大文件摘要不必阻塞 HTTP 响应。
- BackgroundTasks 足够 MVP；任务表保证可观测与重试，后续可换 Celery/ARQ。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 上传与 hash 全同步 | 大文件 P95 超标 |
| 纯消息队列首版 | 运维复杂度高于当前 MVP 需要 |

---

## R3 — 文件用途与分类建议引擎

### Decision

**混合策略（MVP）**：

| 层级 | 手段 | 输出 |
|------|------|------|
| L1 规则 | 文件名关键词 + 扩展名映射表 | `file_purpose` 建议 + 置信度 |
| L2 分类 | 文件名与 Epic 0 别名/同义名模糊匹配 | `product_category_ids`、`chapter_taxonomy_id` 建议 |
| L3 可选 | 文本摘要（docx/pdf 首页抽取）+ LLM | 增强 purpose/分类建议；失败降级 L1+L2 |

建议结果写入 `file_purpose_suggestions` 表；**正式字段仅在用户确认后写入** `file_imports`。

### Rationale

- 符合 constitution G3：机器结果不静默入库。
- SC-004 要求 80% 典型文件名有可辨别建议；规则层可快速达标。
- LLM 作为可选增强，接口与任务日志预留 `suggestion_source=rule|llm`。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 纯 LLM | 延迟高、成本高、需 API Key 才能本地验收 |
| 仅扩展名推断 | 无法满足「餐补模板.docx」类语义 |

---

## R4 — 去重与版本导入

### Decision

- **主键**：`(kb_id, file_hash)` 唯一索引（`file_hash` NOT NULL 时生效）；`hash_status=unavailable`
  时用 `(kb_id, file_name, file_size)` 软匹配提示。
- 重复上传默认返回 `409 DUPLICATE_FILE` + 已有 `import_id` 列表；客户端传
  `duplicate_action=skip|new_version`。
- **新版本**：`parent_import_id` 指向首条或上一版本；`version_no` 递增；独立确认与分流。

### Rationale

- 对齐总需求 §5.4 与 spec FR-011/FR-012。
- `parent_import_id` 满足 spec Assumptions 中版本关系决议。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 全局跨 KB 去重 | 违反 kb 隔离 |
| 硬拒绝重复 | 不满足「作为新版本导入」 |

---

## R5 — 分流与下游任务占位

### Decision

确认保存时写入 `downstream_task_entries`，按 `file_purpose` 映射任务类型：

| file_purpose | downstream_task_type | Epic 消费者 |
|--------------|---------------------|-------------|
| actual_bid | document_parse, bid_outline_extract, candidate_knowledge_generate | Epic 3 |
| template_file | template_file_parse | Epic 2 |
| qualification | manual_asset_candidate | Epic 4 预留 |
| ppt_material, cover_guide, writing_guide | template_material_ingest | Epic 2 素材 |
| wiki_source | wiki_candidate | Epic 4 预留 |
| other | none / attachment_only | — |
| ignored | none | — |

MVP 仅创建 `status=pending` 记录 + 任务中心可见条目；**不执行实际解析**。

### Rationale

- FR-010/FR-019 边界清晰；Epic 2/3 订阅 `pending` 条目即可集成。
- SC-009 以「任务入口可查询、状态正确」验收。

---

## R6 — 并发确认冲突策略

### Decision

**乐观锁**：`file_imports.version`（int，每次确认 +1）；确认 API 要求客户端提交
`expected_version`；不匹配返回 `409 CONFLICT`，提示刷新后重试。后写入操作全量审计。

### Rationale

- 解决 spec Edge Case「并发确认」；比行锁更简单，适合低并发管理后台。

---

## R7 — 文件类型与大小限制

### Decision

| 类型 | 扩展名 | MIME（宽松） | MVP 上限 |
|------|--------|--------------|----------|
| docx | .docx | application/vnd...wordprocessingml | 50 MB |
| pdf | .pdf | application/pdf | 50 MB |
| ppt | .ppt, .pptx | application/vnd...presentation | 50 MB |
| xlsx | .xlsx | application/vnd...spreadsheet | 20 MB |
| image | .png, .jpg, .jpeg, .webp, .gif | image/* | 10 MB |

零字节拒绝；不支持扩展名返回 `VALIDATION` 错误。

### Rationale

- 对齐 spec 支持类型与 Assumptions「plan 阶段确定上限」。
- 分类型上限便于运维调参（`FILE_SIZE_LIMITS` JSON  env）。

---

## R8 — 任务中心与日志模型

### Decision

新增通用 `import_tasks` 表（本 Epic 范围），字段含 `task_type`、`import_id`、`status`、
`log_lines`（JSON array append）、`error_message`、`retry_count`。

任务类型：`file_import`、`file_purpose_classify`；后续 Epic 复用同表或迁移至统一 `platform_tasks`。

### Rationale

- FR-015 要求日志、追溯、重试；独立表比塞入 FileImport JSON 更易查询与任务中心展示。

---

## R9 — 分类引用写入时机

### Decision

用户确认用途并保存后，向 `classification_reference` 写入：

- `object_type=file_import`
- `classification_type=product_category | chapter_taxonomy`
- `source=manual`（用户确认）或 `suggested`（若用户未改建议值）

Epic 0 表已预留 `object_type`；Epic 1 扩展 enum 增加 `file_import`。

### Rationale

- 统一影响分析与全链路追溯；复用 Epic 0 基础设施。
