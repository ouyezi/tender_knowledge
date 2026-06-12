# Design: Epic 2 模板库解析与发布

**Date**: 2026-06-12  
**Status**: Approved  
**Feature spec**: `specs/003-template-parse-publish/spec.md`  
**Implementation plan (Spec Kit)**: `specs/003-template-parse-publish/plan.md`  
**Superpowers plan**: `docs/superpowers/plans/2026-06-12-epic2-template-parse-publish.md`

## 1. 背景与目标

Epic 2 在 Epic 1 已确认 `file_purpose=template_file` 并写入 `downstream_task_entries`
（`template_file_parse`）的前提下，完成 **docx 模板文件 → Template 结构化资产 → 人工确认 →
章节树编辑 → 模板库发布** 全链路。产出 Candidate Knowledge 占位供 Epic 4；已发布 Template
Library 供 Epic 5/6 消费。

本设计在 Spec Kit 制品基础上，补充 brainstorming 决议的 **双入口 UX、全屏确认向导、P0–P4
交付切片、LLM 降级、重解析 diff、与 Epic 1/4/5 集成边界**。

## 2. 设计决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 主入口 | **双入口**：来源导入中心 = 解析状态/重试；模板库中心 = 确认→编辑→发布 |
| D2 | 解析确认 UI | **全屏分步向导** Step1 归类 → Step2 章节树 → Step3 素材/候选；路由 `/template-libraries/parse-confirm/:parseTaskId` |
| D3 | 解析启动 | **自动启动**：Epic 1 确认 `template_file` 后立即 claim downstream 并解析 |
| D4 | 章节树编辑 | **拖拽树 + 属性面板**：左侧 Tree draggable；右侧编辑标题/章节类型/产品分类/必填 |
| D5 | 模板库中心首页 | **待办优先**：顶部待确认/解析中/失败任务区 + 下方 Template Library 列表 |
| D6 | 建议引擎 | **规则为主**（Heading 样式 + 编号 + 文件名匹配 Epic 0）；`LLM_API_KEY` 可选增强章节类型；失败降级 |
| D7 | 重解析 | 已 `structure_locked` → `template_structure_diff`；待办区展示「结构差异待审」 |
| D8 | 导入中心扩展 | 列表增 `parse_status` 列；操作：任务日志、重试；**无**解析确认/章节编辑 |
| D9 | 导航 | AppShell 增加「模板库」→ `/template-libraries`；依赖 KBContext |
| D10 | 异步模型 | **FastAPI BackgroundTasks** + `template_parse_tasks`；复用 Epic 1 trace/audit 模式 |
| D11 | inactive KB | 与 Epic 0/1 一致：只读，禁止解析/确认/发布 |
| D12 | docx 解析 | **python-docx**；无 Heading 时扁平树 + `needs_manual_review` 标记 |

## 3. 架构与交付切片

### 3.1 交付顺序

```text
P0  模板域基建（表、审计、路由壳、模板库中心空页、导入中心 parse_status 列）
  → P1  自动解析 pipeline（claim downstream → docx → parse_ready）
  → P2  全屏确认向导 + structure lock + 待办区联动
  → P3  拖拽章节树 + 素材/变量/规则面板
  → P4  发布/版本/废弃 + candidate stubs + 重解析 diff 审阅
```

### 3.2 P0 — 模板域基建

| 能力 | 说明 |
|------|------|
| ORM 表 | `template_libraries`, `templates`, `template_chapters`, `template_materials`, `template_variables`, `template_rules`, `template_parse_tasks`, `template_parse_suggestions`, `template_structure_diffs`, `candidate_knowledge_stubs`, `template_publish_snapshots`, `template_audit_logs` |
| 依赖 | `python-docx` 加入 `pyproject.toml` |
| 引用扩展 | `classification_reference.object_type` 增加 `template_library`, `template`, `template_chapter`, `template_material` |
| API 壳 | 注册 `template_parse`, `template_libraries`, `templates`, `template_chapters`, `template_assets` routers |
| UI 壳 | `/template-libraries` + 导航；待办区/库列表空态；导入中心 `parse_status` 列占位 |
| 审计 | `template_audit_log`；复用 `AuditMiddleware` |

**P0 验收**：表可创建；inactive KB 写操作 403；双导航可进入空页。

### 3.3 P1 — 自动解析

- `template_parse_runner`：轮询/BackgroundTasks claim `downstream_task_entries` where `template_file_parse` + `pending`
- `docx_outline_parser`：Heading 1–9 / 中文标题样式 + 前缀编号 → 章节树
- `docx_content_extractor`：段落/表格/图片 → `template_materials` draft
- `variable_detector`：扫描 `{{key}}` → variables draft
- 创建 `template_parse_tasks`：`running` → `parse_ready`；写入 `template_parse_suggestions`
- 绑定 `templates` draft（`confirmed=false`）
- 导入中心：`parse_status` = 解析中 / 待确认 / 失败；`POST .../template-parse/trigger` retry

**P1 验收**：Epic 1 确认 template_file 后 60s 内（50 页 docx）到达 `parse_ready`；失败不破坏 File Import；sample-template.docx 章节树非空。

### 3.4 P2 — 解析确认向导

- 路由：`/template-libraries/parse-confirm/:parseTaskId`
- Step1：Template Library 选择/新建、产品分类、`template_name`/`template_type`
- Step2：章节树预览（可改层级/类型/ignore/required）；无 Heading 时展示「待整理」Alert
- Step3：Material 列表 + Candidate 提取意向（ku/wiki/忽略）
- `POST .../template-parse/tasks/{id}/confirm` → `structure_locked_at` + `confirmed=true`
- 模板库中心待办：「待确认」→ 跳转向导

**P2 验收**：确认后 parse_task=`confirmed`；再次 GET 树与确认提交一致；未确认前无 published 资产。

### 3.5 P3 — 章节与素材编辑

- 路由：`/template-libraries/templates/:templateId`
- `ChapterTreeEditor`：Ant Design Tree `draggable` + `onDrop` → `POST .../chapters/batch-update`
- `ChapterPropertyPanel`：选中节点编辑属性
- Tabs：`素材` / `变量` / `规则`（MVP 规则类型限制）
- `template_audit_log`：`chapter_update`, `material_update` 等

**P3 验收**：拖拽/属性修改保存后刷新一致；SC-004 100% 反映编辑结果。

### 3.6 P4 — 发布与下游

- `POST .../template-libraries/{id}/publish`：校验 required 规则、必填变量、章节非空
- `template_publish_snapshots` 写入；`status=published`；级联 Template（`cascade_templates=true`）
- `candidate_knowledge_stubs`：`pending_confirm` 供 Epic 4
- 已发布只读 API：`GET ...?status=published`（Epic 5 前置）
- 重解析：`force_reparse` → `template_structure_diff`；待办「结构差异待审」→ apply/reject

**P4 验收**：未发布库推荐查询为空；发布后 snapshot 可查；stub 列表有记录；diff 不静默覆盖已锁定树。

### 3.7 明确不在范围

- Bid Outline → Template、Template Instance、招标约束章节草稿
- conditional / mutex / asset_required 规则、复杂变量表达式
- Candidate Knowledge 工作台 UI（Epic 4）、模块推荐（Epic 5）
- 文件夹批量建 Template Library、全局任务中心页

## 4. 组件与模块边界

### 4.1 后端（`backend/src/`）

| 模块 | 职责 | 切片 |
|------|------|------|
| `models/template_*.py` | ORM | P0 |
| `services/template_parse_runner.py` | claim + 编排解析 | P1 |
| `services/docx_outline_parser.py` | 标题树 | P1 |
| `services/docx_content_extractor.py` | Material / stub | P1 |
| `services/variable_detector.py` | `{{key}}` | P1 |
| `services/template_confirm_service.py` | 向导 confirm + lock | P2 |
| `services/template_publish_service.py` | 发布校验 + snapshot | P4 |
| `api/routes/template_parse.py` 等 | HTTP | P1–P4 |

### 4.2 前端（`frontend/src/`）

| 模块 | 职责 | 切片 |
|------|------|------|
| `layout/AppShell.tsx` | 导航「模板库」 | P0 |
| `pages/TemplateLibraryCenter/index.tsx` | 待办区 + 库列表 | P0, P2 |
| `ParseConfirmWizard.tsx` | 三 Step 全屏向导 | P2 |
| `TemplateDetailPage.tsx` | 树编辑 + Tabs | P3 |
| `ChapterTreeEditor.tsx` | 拖拽树 | P3 |
| `ChapterPropertyPanel.tsx` | 节点属性 | P3 |
| `MaterialPanel.tsx` / `VariableRulePanel.tsx` | 资产 Tab | P3 |
| `PublishModal.tsx` | 发布 | P4 |
| `FileImportCenter/index.tsx` | `parse_status` 列 + retry 跳转 | P1 |
| `services/templates.ts` | API client | P1–P4 |

### 4.3 依赖原则

- Routes 薄；解析与确认逻辑在 services。
- 分类选项仅来自 Epic 0 读 API。
- 读 Epic 1 `file_imports.storage_path`；不重复落盘。
- Epic 4 只读/更新 `candidate_knowledge_stubs`；Epic 5 只读 published 模板域。

## 5. 数据流

### 5.1 自动解析（D3）

```text
Epic 1 POST .../file-imports/{id}/confirm (file_purpose=template_file)
  → create_downstream_entries(template_file_parse, pending)
  → BackgroundTasks.enqueue(template_parse_runner.poll_or_run):
       claim downstream entry
       INSERT template_parse_task (running)
       READ file from STORAGE_ROOT via import.storage_path
       docx_outline_parser → suggested_chapter_tree
       docx_content_extractor → materials + candidate stubs (draft)
       variable_detector → variables draft
       UPSERT template (draft, confirmed=false)
       UPSERT template_parse_suggestion
       UPDATE parse_task status=parse_ready
       template_audit_log (parse_complete)
       UPDATE downstream entry completed
  ON failure:
       parse_task status=failed, error_message
       downstream failed (or pending for retry)
       file_import UNCHANGED
```

### 5.2 确认向导（D2）

```text
TemplateLibraryCenter 待办 → navigate /parse-confirm/:parseTaskId
  Step1–3 user edits
  → POST .../template-parse/tasks/{id}/confirm
  → template_confirm_service.apply:
       persist library assignment (nullable = 未归类)
       replace chapter tree from payload
       create materials, candidate_knowledge_stubs per candidate_actions
       SET structure_locked_at, confirmed=true
       parse_task status=confirmed
  → redirect /template-libraries/templates/:templateId
```

### 5.3 章节编辑（D4）

```text
Tree onDrop / PropertyPanel save
  → debounce or explicit Save
  → POST .../templates/{id}/chapters/batch-update
  → validate tree integrity (level, parent)
  → UPDATE chapters + audit (chapter_update)
```

### 5.4 重解析 diff（D7）

```text
POST .../template-parse/trigger { force_reparse: true }
  IF template.structure_locked_at IS NOT NULL:
       run parse → INSERT template_structure_diff (pending_review)
       DO NOT mutate locked chapters
  ELSE:
       overwrite draft tree + new suggestion
  待办区 → DiffReviewDrawer → POST .../diff/apply | reject
```

### 5.5 LLM 降级（D6）

```text
IF not settings.llm_api_key: suggestion_source=rule
ELSE:
  snippet = heading_titles + first paragraphs
  llm_suggest chapter_taxonomy_id per node
  ON error: log + keep rule-only taxonomy from filename/alias match
```

### 5.6 导入中心只读状态（D1/D8）

```text
GET file-imports list enriched with latest parse_task.status
  → 解析中 | 待确认 | 失败 | —
  Actions:
    失败 → POST template-parse/retry
    待确认 → Link to /template-libraries?highlight=:parseTaskId
  NO confirm/edit/publish on this page
```

## 6. 数据模型补充（相对 data-model.md）

无结构变更；本设计锁定：

- `templates.template_library_id` nullable = 未归类（D1）
- `structure_locked_at` 写入时机 = 向导 confirm 成功（D2）
- `parse_ready` 为人工确认门状态；`published` 为 Epic 5 可见门
- `candidate_knowledge_stubs.status=pending_confirm` 为 Epic 4 入口

## 7. API 契约

沿用 `specs/003-template-parse-publish/contracts/`：

- `template-parse-api.md` — trigger, tasks, suggestion, confirm, diff, retry
- `template-library-api.md` — libraries, templates, publish, snapshots
- `template-chapter-api.md` — tree, batch-update, move, reorder
- `template-asset-api.md` — materials, variables, rules, stubs

错误码补充：

| code | 场景 |
|------|------|
| `PARSE_IN_PROGRESS` | 重复 trigger 时已有 running 任务 |
| `INVALID_STATE` | 非 parse_ready 时 confirm |
| `PUBLISH_VALIDATION` | 发布校验失败（required 章节/变量） |
| `CONFLICT` | batch-update 并发冲突 |
| `KB_READ_ONLY` | inactive KB 写操作 |

## 8. 错误处理

- 统一 envelope + `trace_id`
- 解析失败：File Import 不变；导入中心可 retry；错误信息写入 parse_task
- 无 Heading 文档：parse_ready + 扁平树，非 failed
- 源文件不可读：failed + 明确 error_message
- 未发布/未确认：对外推荐 API 返回空集，不 403 泄露 draft 存在性

## 9. 测试策略

| 切片 | 关键测试 |
|------|----------|
| P0 | 模型 create_all；router 注册；inactive KB 403 |
| P1 | downstream claim；sample-template.docx 树；parse 失败保留 import |
| P2 | confirm 三 step payload；structure_locked；锁定后树不被重解析覆盖 |
| P3 | batch-update 拖拽等价；属性 PATCH |
| P4 | publish 校验；snapshot；stubs；diff apply/reject |

- 后端：`tests/unit/test_docx_outline_parser.py`、`tests/integration/test_template_parse_flow.py`、contract tests
- 夹具：`backend/tests/fixtures/sample-template.docx`
- 前端：向导 Step 流转、Tree onDrop 冒烟（可选 Vitest）

## 10. 与 Spec Kit 制品同步项

1. `specs/003-template-parse-publish/plan.md` — 模块路径与 Constitution Check 已对齐
2. `research.md` / `data-model.md` / `contracts/` — 本设计 D1–D12 为 UX/切片补充，不冲突
3. `tasks.md` — 由 `/speckit-tasks` 或 Superpowers plan 生成时映射 P0–P4

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| BackgroundTasks 丢任务 | `template_parse_tasks` 留 failed；retry API；downstream 可重 claim |
| docx 样式不标准 | 编号启发式 + 扁平降级 + Step2 人工整理 |
| 大树拖拽性能 | 单 Template ≤200 节点 MVP 假设；batch-update 一次提交 |
| 向导 Step2/Step3 状态丢失 | 前端每 Step 本地 state；最终一次 confirm POST |
| LLM 不可用 | 可选；规则降级（D6） |

## 12. 审批记录

| 阶段 | 状态 | 日期 |
|------|------|------|
| Brainstorming D1–D5 | 已确认 | 2026-06-12 |
| §1–§9 设计草案 | 已确认 | 2026-06-12 |
| 设计文档书面审阅 | 已确认（用户「批准文档」） | 2026-06-12 |
| Superpowers 实现计划 | 已生成 | 2026-06-12 |
