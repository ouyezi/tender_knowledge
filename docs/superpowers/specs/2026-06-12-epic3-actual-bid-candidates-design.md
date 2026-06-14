# Design: Epic 3 实际标书导入与候选知识

**Date**: 2026-06-12  
**Status**: Approved (brainstorming)  
**Feature spec**: `specs/004-actual-bid-candidates/spec.md`  
**Implementation plan (Spec Kit)**: `specs/004-actual-bid-candidates/plan.md`  
**Superpowers plan**: `docs/superpowers/plans/2026-06-12-epic3-actual-bid-candidates.md`

## 1. 背景与目标

Epic 3 在 Epic 1 已确认 `file_purpose=actual_bid` 并写入三条 `downstream_task_entries`
（`document_parse`、`bid_outline_extract`、`candidate_knowledge_generate`）的前提下，完成
**docx 实际标书 → Document/Document Tree → Bid Outline → Candidate Knowledge（pending）**
解析链路前半段。产出待 Epic 4 确认的候选与模式资产；已确认 Bid Outline 供 Epic 5 目录级检索。

本设计在 Spec Kit 制品基础上，补充 brainstorming 决议的 **全屏解析确认向导、向导不锁定目录、
双入口 UX、P0–P4 交付切片、与 Epic 2 对称的自动解析与 LLM 降级、重解析 diff**。

## 2. 设计决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 解析后第一站 | **全屏确认向导**（仿 Epic 2 选项 A） |
| D2 | 向导结束是否 structure_lock | **否**（选项 B）；目录中心单独「确认目录」 |
| D3 | 整体架构 | **Epic 2 对称**：双入口 + 自动解析（方案 ①） |
| D4 | 向导 Step | Step1 元数据 → Step2 目录+分类 → Step3 候选只读预览 |
| D5 | parse_task 状态 | `ready`（可进向导）→ `confirmed`（向导完成） |
| D6 | 主入口 | **双入口**：来源导入中心 = 状态/重试；目录中心 = 待办/向导/深度编辑 |
| D7 | 解析启动 | **自动启动**：Epic 1 确认 `actual_bid` 后立即 claim downstream 并解析 |
| D8 | 目录深度编辑 | **拖拽树 + 属性面板**；路由 `/outlines/:bidOutlineId` |
| D9 | 目录中心首页 | **待办优先**：待确认解析 / 解析中 / 失败 / 结构差异 / 待确认目录 |
| D10 | 候选中心 | `/candidates` **只读** pending 列表；无确认/发布（Epic 4） |
| D11 | 建议引擎 | **规则为主** + 可选 LLM（复用 Epic 2 `llm_client`）；失败降级 |
| D12 | 重解析 | 已 `structure_locked` → `bid_outline_structure_diff`；待办审阅 apply/reject |
| D13 | 导入中心扩展 | `parse_status` 列对 actual_bid 显示；操作：重试、跳转向导 |
| D14 | 导航 | AppShell 增加「目录」「候选」；依赖 KBContext |
| D15 | 异步模型 | **FastAPI BackgroundTasks** + `actual_bid_parse_tasks` |
| D16 | inactive KB | 与 Epic 0/1/2 一致：只读，禁止解析/确认/锁定 |
| D17 | docx 解析 | **python-docx** 全文树；**lxml** TOC 优先 → Heading 启发式降级 |
| D18 | 候选存储 | 新建 **`candidate_knowledges`**（document 来源）；列表 API 聚合 template `stubs` |

## 3. 架构与交付切片

### 3.1 交付顺序

```text
P0  实际标书域基建（表、审计、路由壳、目录/候选空页、parse_status 扩展）
  → P1  自动解析 pipeline（三阶段 downstream → ready）
  → P2  全屏确认向导 + 待办区联动（不 structure_lock）
  → P3  目录详情深度编辑 + 「确认目录」+ diff 审阅
  → P4  候选只读中心 + Chapter Pattern 挖掘 + 重解析闭环
```

### 3.2 P0 — 实际标书域基建

| 能力 | 说明 |
|------|------|
| ORM 表 | `documents`, `document_tree_nodes`, `bid_outlines`, `bid_outline_nodes`, `actual_bid_parse_tasks`, `document_parse_suggestions`, `bid_outline_structure_diffs`, `candidate_knowledges`, `chapter_patterns`, `chapter_pattern_mining_tasks`, `actual_bid_audit_logs` |
| 依赖 | `python-docx`, `lxml`（若 Epic 2 已引入则复用） |
| API 壳 | 注册 `actual_bid_parse`, `bid_outlines`, `candidates`, `chapter_patterns` routers |
| UI 壳 | `/outlines`, `/candidates` + 导航；待办/列表空态；导入中心 `parse_status` 对 actual_bid |
| 审计 | `actual_bid_audit_log`；复用 `AuditMiddleware` |

**P0 验收**：表可创建；inactive KB 写操作 403；双导航可进入空页。

### 3.3 P1 — 自动解析

- `actual_bid_parse_runner`：BackgroundTasks claim 三条 downstream（串行）
- `docx_document_walker`：Heading 栈 + 段落/表格/图片 → `document_tree_nodes`
- `docx_toc_extractor`：内置 TOC 优先 → fallback `docx_outline_parser`
- `bid_outline_extract_service`：`bid_outlines` + `bid_outline_nodes`（`source_node_id`）
- `chunk_classification_service`：块级分类建议 → `document_parse_suggestions`
- `candidate_generate_service`：`candidate_knowledges`（`status=pending`）
- 导入中心：`parse_status` = 解析中 / 待确认 / 失败；`POST .../actual-bid-parse/trigger` retry

**P1 验收**：Epic 1 确认 actual_bid 后 120s 内（50 页 docx）到达 `ready`；失败不破坏 File Import；下游三条 completed。

### 3.4 P2 — 解析确认向导

- 路由：`/outlines/parse-confirm/:parseTaskId`
- Step1：项目名、客户、产品分类、`source_usage`
- Step2：Bid Outline 树预览（可改标题/层级/排序）+ 章节类型 + 产品分类
- Step3：本次 `candidate_knowledges` **只读**列表（条数 + 来源链摘要）
- `POST .../actual-bid-parse/tasks/{id}/confirm` → `parse_task.status=confirmed`
- **不**写入 `structure_locked_at`；`bid_outline.status` 保持 `draft`
- 目录中心待办：「待确认解析」→ 跳转向导
- 完成后 redirect `/outlines/:bidOutlineId`

**P2 验收**：向导完成后元数据与分类持久化；`parse_task=confirmed`；**无** structure_lock。

### 3.5 P3 — 目录深度编辑与锁定

- 路由：`/outlines/:bidOutlineId`
- `OutlineTreeEditor`：Ant Design Tree `draggable` + 属性面板（章节类型、产品分类）
- 支持合并/删除节点 batch ops
- `POST .../bid-outlines/{id}/confirm` → `structure_locked_at` + `status=confirmed`
- `bid_outline_structure_diff`：重解析后 DiffDrawer → apply/reject
- 编辑 Bid Outline **不**修改 Document Tree

**P3 验收**：拖拽/合并保存后刷新一致（SC-004）；锁定后重解析仅 diff，不静默覆盖。

### 3.6 P4 — 候选与模式挖掘

- `GET .../candidates`：聚合 `candidate_knowledges` + `candidate_knowledge_stubs`（只读）
- `CandidateCenter`：筛选 `pending`；无确认按钮
- `POST .../chapter-patterns/mine`：批任务 `chapter_pattern_mining`
- 目录中心入口：「挖掘章节模式」
- 未确认候选不参与检索（SC-006）

**P4 验收**：候选 100% 可追溯到 import/document/node；模式 `status=candidate`；diff 闭环可用。

### 3.7 明确不在范围

- Candidate Knowledge 确认、合并、拆分、发布（Epic 4）
- 目录级检索与模块建议（Epic 5）
- 招标文件评分点、废标项解析
- `candidate_knowledge_stubs` 表结构重构（Epic 4 统一）
- Bid Outline → Template Draft
- 文件夹批量导入、全局任务中心页

## 4. 组件与模块边界

### 4.1 后端（`backend/src/`）

| 模块 | 职责 | 切片 |
|------|------|------|
| `models/document*.py`, `bid_outline*.py` | ORM | P0 |
| `models/candidate_knowledge.py`, `chapter_pattern*.py` | ORM | P0 |
| `services/actual_bid_parse_runner.py` | claim + 三阶段编排 | P1 |
| `services/docx_document_walker.py` | 全文 Document Tree | P1 |
| `services/docx_toc_extractor.py` | TOC 优先抽取 | P1 |
| `services/bid_outline_extract_service.py` | Outline 生成 | P1 |
| `services/candidate_generate_service.py` | 候选写入 | P1 |
| `services/actual_bid_confirm_service.py` | 向导 confirm（无 lock） | P2 |
| `services/bid_outline_diff_service.py` | 重解析 diff | P3–P4 |
| `services/chapter_pattern_miner.py` | 模式挖掘 | P4 |
| `api/routes/actual_bid_parse.py` 等 | HTTP | P1–P4 |

### 4.2 前端（`frontend/src/`）

| 模块 | 职责 | 切片 |
|------|------|------|
| `layout/AppShell.tsx` | 导航「目录」「候选」 | P0 |
| `pages/OutlineCenter/index.tsx` | 待办区 + 列表 | P0, P2 |
| `ActualBidParseConfirmWizard.tsx` | 三 Step 全屏向导 | P2 |
| `OutlineDetailPage.tsx` | 树编辑 + 确认目录 | P3 |
| `OutlineDiffDrawer.tsx` | diff 审阅 | P3–P4 |
| `CandidateCenter/index.tsx` | 只读列表 | P4 |
| `FileImportCenter/index.tsx` | `parse_status` + retry 跳转 | P1 |
| `services/actualBidParse.ts`, `bidOutlines.ts`, `candidates.ts` | API client | P1–P4 |

### 4.3 依赖原则

- Routes 薄；解析与确认逻辑在 services。
- 分类选项仅来自 Epic 0 读 API。
- 读 Epic 1 `file_imports.storage_path`；不重复落盘。
- 复用 Epic 2：`docx_outline_parser`, `llm_client`, `chunk_classification_service`。
- Epic 4 消费 `candidate_knowledges`（pending）+ stubs；Epic 5 只读 `confirmed` outline。

## 5. 数据流

### 5.1 自动解析（D7）

```text
Epic 1 POST .../file-imports/{id}/confirm (file_purpose=actual_bid)
  → create_downstream_entries ×3 (pending)
  → BackgroundTasks.enqueue(actual_bid_parse_runner):
       claim document_parse
       INSERT actual_bid_parse_task (running)
       READ file from STORAGE_ROOT
       docx_document_walker → documents + document_tree_nodes
       mark document_parse completed
       claim bid_outline_extract
       docx_toc_extractor → bid_outlines + bid_outline_nodes
       chunk_classification_service → document_parse_suggestions
       mark bid_outline_extract completed
       claim candidate_knowledge_generate
       candidate_generate_service → candidate_knowledges (pending)
       mark candidate_knowledge_generate completed
       parse_task status=ready
       actual_bid_audit_log (parse_complete)
  ON failure:
       parse_task status=failed, error_message
       当前 downstream failed；file_import UNCHANGED
```

### 5.2 确认向导（D1/D2/D4）

```text
OutlineCenter 待办 → navigate /outlines/parse-confirm/:parseTaskId
  Step1: PATCH document metadata
  Step2: PATCH outline nodes (tree + taxonomy)
  Step3: GET candidates preview (read-only)
  → POST .../actual-bid-parse/tasks/{id}/confirm
  → actual_bid_confirm_service.apply:
       persist document metadata
       persist outline node edits + classifications
       parse_task status=confirmed
       DO NOT set structure_locked_at
  → redirect /outlines/:bidOutlineId
```

### 5.3 目录锁定（D2）

```text
OutlineDetailPage 用户完成合并/删除/微调
  → POST .../bid-outlines/{id}/confirm
  → SET structure_locked_at, status=confirmed
  → actual_bid_audit_log (outline_confirmed)
```

### 5.4 重解析 diff（D12）

```text
POST .../actual-bid-parse/trigger { force_reparse: true }
  IF bid_outline.structure_locked_at IS NOT NULL:
       run parse → INSERT bid_outline_structure_diff (pending)
       DO NOT mutate locked outline nodes
  ELSE:
       update draft outline + new suggestion
  待办区 → OutlineDiffDrawer → POST .../diffs/{id}/apply | reject
```

### 5.5 LLM 降级（D11）

```text
IF not settings.llm_api_key: suggestion_source=rule
ELSE:
  per chapter block: llm_suggest taxonomy + knowledge_type
  ON error: log + rule-only from chapter_candidate_rules.yaml
```

### 5.6 导入中心只读状态（D6/D13）

```text
GET file-imports list enriched with latest actual_bid_parse_task.status
  → 解析中 | 待确认 | 已确认向导 | 失败 | —
  Actions:
    失败 → POST actual-bid-parse/trigger
    待确认 → Link to /outlines/parse-confirm/:parseTaskId
  NO outline edit / candidate confirm on this page
```

## 6. 数据模型补充（相对 data-model.md）

Brainstorming 追加/锁定项：

| 项 | 变更 |
|----|------|
| `actual_bid_parse_tasks.status` | 增加 `confirmed`（向导完成后） |
| `structure_locked_at` 写入时机 | **仅** `POST .../bid-outlines/{id}/confirm`（D2），**非**向导 confirm |
| `candidate_knowledges` | document 路径 canonical 表；stub 保留 template 路径 |
| `parse_ready` / `ready` | 人工向导门；`confirmed` outline 为 Epic 5 可见门 |
| File Import `parse_status` | 扩展映射 actual_bid 任务状态（见 §3.3） |

**契约同步**（实现前更新 `contracts/actual-bid-parse-api.md`）：

- `parse_task_status` 增加 `confirmed`
- 新增 `POST .../actual-bid-parse/tasks/{id}/confirm`（向导提交体同 Step1+2 聚合 payload）

## 7. API 契约

沿用 `specs/004-actual-bid-candidates/contracts/`：

- `actual-bid-parse-api.md` — trigger, tasks, document, tree, **confirm（新增）**
- `bid-outline-api.md` — list, nodes, batch, **outline confirm（structure lock）**, diff
- `bid-candidate-api.md` — candidates 只读列表, chapter pattern mine

错误码补充：

| code | 场景 |
|------|------|
| `PARSE_IN_PROGRESS` | 重复 trigger |
| `INVALID_STATE` | 非 `ready` 时向导 confirm |
| `OUTLINE_NOT_LOCKED` | 非 confirmed 状态访问 Epic 5 预留端点时（本 Epic 不实现检索） |
| `DIFF_NOT_PENDING` | diff 已处理 |
| `KB_READ_ONLY` | inactive KB 写操作 |

## 8. 错误处理

- 统一 envelope + `trace_id`
- 解析失败：File Import 不变；可 retry
- 无 TOC/无 Heading：扁平 outline + `needs_manual_review`；仍 `ready`
- 源文件不可读：`failed` + `error_message`
- 单章内容过短：跳过该章候选，记 reason；任务不整体失败
- 未确认候选：检索 API 返回空集（本 Epic 不实现检索，仅保证列表隔离）

## 9. 测试策略

| 切片 | 关键测试 |
|------|----------|
| P0 | 模型 create_all；router 注册；inactive KB 403 |
| P1 | downstream 三阶段 claim；sample-actual-bid.docx；失败保留 import |
| P2 | 向导 confirm payload；**无** structure_lock；`parse_task=confirmed` |
| P3 | outline batch ops；`POST confirm` 锁定；diff apply/reject |
| P4 | candidates 来源链；pattern mining；聚合列表含 stub |

- 后端：`tests/unit/test_docx_toc_extractor.py`、`tests/integration/test_actual_bid_flow.py`、contract tests
- 夹具：`backend/tests/fixtures/sample-actual-bid.docx`
- 前端：向导 Step 流转、确认目录按钮冒烟（可选 Vitest）

## 10. 与 Spec Kit 制品同步项

1. `specs/004-actual-bid-candidates/plan.md` — 模块路径已对齐；本设计补充 P0–P4 与 UX 决议
2. `contracts/actual-bid-parse-api.md` — 需增补 `confirmed` 状态与向导 confirm 端点
3. `tasks.md` — 由 `/speckit-tasks` 映射 P0–P4（建议按本设计切片排序）

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| BackgroundTasks 丢任务 | `actual_bid_parse_tasks` 留 failed；trigger retry；downstream 可重 claim |
| TOC 解析不稳定 | lxml + 降级 heading；`needs_manual_review`；Step2 人工整理 |
| 双轨理解成本 | UI 明示「目录编辑不影响正文树」；来源链展示 source_node_id |
| 向导与目录中心两步操作 | 待办区分「待确认解析」vs「待确认目录」 |
| 候选双表聚合 | 统一 list DTO；Epic 4 再收敛存储 |
| LLM 不可用 | 规则降级（D11） |

## 12. 审批记录

| 阶段 | 状态 | 日期 |
|------|------|------|
| Brainstorming D1（向导） | 已确认 | 2026-06-12 |
| Brainstorming D2（不 lock） | 已确认 | 2026-06-12 |
| §1–§6 设计草案 | 已确认 | 2026-06-12 |
| 设计文档书面审阅 | 已确认 | 2026-06-12 |
| Superpowers 实现计划 | 已生成 | 2026-06-12 |
