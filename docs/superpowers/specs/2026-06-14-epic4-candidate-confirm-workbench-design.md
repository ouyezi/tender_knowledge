# Design: Epic 4 候选知识确认工作台

**Date**: 2026-06-14  
**Status**: Draft (brainstorming — pending user review)  
**Feature spec**: `specs/006-candidate-confirm-workbench/spec.md`  
**Implementation plan (Spec Kit)**: `specs/006-candidate-confirm-workbench/plan.md`  
**Epic source**: `docs/epics/epic4-候选知识确认工作台.md`

## 1. 背景与目标

Epic 2/3 已产出 **pending** Candidate Knowledge（`candidate_knowledges` + `candidate_knowledge_stubs`
聚合列表）。Epic 4 完成 V3.0-MVP **治理闭环**：人工审阅 → 编辑 → 合并/拆分/忽略 →
**发布为正式知识资产**，并保留 `candidate_id` 来源链；未确认候选与 Epic 5 检索严格隔离。

本设计在 Spec Kit 制品（spec / plan / research / contracts）基础上，补充 brainstorming 决议的
**混合 UX、全量 7 种 confirm_as、批量 Modal+结果 Drawer、全屏发布两栏 Tab 布局、P0–P4 交付切片**。

## 2. Brainstorming 决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 主交互形态 | **混合模式**：`/candidates` 列表 + Drawer 预览/轻编辑；重操作走全屏 |
| D2 | MVP 发布类型 | **全部 7 种** `confirm_as`（与 spec 一致，首版即完整闭环） |
| D3 | 批量确认 UX | **轻量 Modal + 结果 Drawer**；失败项跳转全屏发布页重试 |
| D4 | 全屏发布页 | **两栏固定布局**：左只读（来源+正文）；右 Tab「编辑/发布」；`confirm_as` 动态字段 |
| D5 | 双源 ID | 保留 `doc_{uuid}` / `tpl_{uuid}`；`CandidateAdapter` 统一读写 |
| D6 | 后端发布 | **单入口编排器** `candidate_publish_service` + 类型 publisher |
| D7 | 正式表 | 新建 `knowledge_units` / `wikis` / `manual_assets`；复用 template_chapter / chapter_pattern / product_category |
| D8 | 幂等 | `status=published` + `confirmed_object_id` 存在 → 200 幂等返回 |
| D9 | 审计 | 独立 `candidate_confirm_audit_logs`；批量写批次头 + items |
| D10 | 检索隔离 | Epic 4 不实现检索；正式对象 `searchable` 门；契约负向测试 |

## 3. 实现路径对比（Brainstorming）

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| ① 后端先行 | 全部 API + publisher 完成后再做 UI | 契约稳定 | 验收滞后、UX 风险后置 |
| ② 按 confirm_as 竖切 | 每种类型独立前后端小闭环 | 可并行 | 编排器/审计重复建设 |
| **③ 分层竖切（推荐）** | P0 基建 → P1 单条全链路（7 类型）→ P2 合并/拆分/批量 → P3 审计 UI → P4  polish | 早验收核心闭环；与 Epic 2/3 节奏一致 | 需严格 P0 阻塞项 |

**推荐 ③**：P1 结束即可演示「选候选 → 全屏发布 → 正式 KU/Wiki/…」；P2 叠加治理效率能力。

## 4. 架构

### 4.1 前后端边界

```text
┌─────────────────────────────────────────────────────────────┐
│  CandidateCenter (/candidates)                              │
│  ├─ ProTable 列表 + 筛选 + 多选                              │
│  ├─ Drawer：预览、轻量 PATCH（标题/摘要/分类建议）            │
│  ├─ Modal：批量策略（统一 KU / 全部忽略 / 沿用建议类型）      │
│  ├─ Result Drawer：逐条成功/失败                             │
│  └─ 跳转全屏发布 / 批量失败重试                               │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  CandidateConfirmPage (/candidates/confirm/:candidateId)   │
│  ├─ 左栏：来源链 Descriptions + 正文只读/可折叠               │
│  └─ 右栏 Tab：编辑 | 发布（confirm_as 动态 Form）            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  API Layer                                                  │
│  PATCH /candidates/{id}                                   │
│  POST  /candidates/{id}/confirm | /retry-publish          │
│  POST  /candidates/merge | /{id}/split                      │
│  POST  /candidates/batch/confirm | /batch/reject          │
│  GET   /candidate-audit-logs                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Services                                                   │
│  candidate_adapter → edit / merge / publish_validator       │
│  candidate_publish_service → publishers/* (7+ignore)        │
│  candidate_audit_service                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL                                                 │
│  candidate_* (extended) | knowledge_units | wikis           │
│  manual_assets | template_chapters | chapter_patterns       │
│  product_categories | candidate_confirm_audit_logs          │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 confirm_as → 正式对象映射

| confirm_as | Publisher | 正式对象 |
|------------|-----------|----------|
| ku | `ku_publisher` | INSERT `knowledge_units` |
| wiki | `wiki_publisher` | INSERT `wikis` |
| template_chapter | `template_chapter_publisher` | INSERT/UPDATE `template_chapters`（stub.template_id） |
| manual_asset | `manual_asset_publisher` | INSERT `manual_assets` |
| chapter_pattern | `chapter_pattern_publisher` | UPDATE `chapter_patterns.status=confirmed` |
| product_category | `product_category_publisher` | INSERT `product_categories` |
| ignore | `ignore_handler` | 候选 `status=rejected` |

每次成功发布：回写 `confirmed_object_type/id`、`status=published`、写 audit、`trace_id`。

### 4.3 CandidateAdapter

- 解析 `doc_` / `tpl_` 前缀 → 查 `candidate_knowledges` 或 `candidate_knowledge_stubs`
- 统一 `CandidateView` dataclass（title, content, status, source_trace, channel, …）
- 写操作：仅 `pending` / `pending_confirm` 可编辑；终态抛 `CANDIDATE_NOT_EDITABLE`

## 5. UI 设计

### 5.1 列表页 `/candidates`

- **ProTable** 替换现有 Table：筛选（import_id、product_category、chapter_taxonomy、candidate_type、status、source_channel、confidence_min）
- **行操作**：查看（Drawer）、发布（跳转全屏）
- **工具栏**：批量确认、批量驳回、刷新
- **Drawer（轻编辑）**：只读元数据 + 可 PATCH 标题/摘要/建议分类；底部「保存」「前往发布」
- 不承载完整 7 类型发布表单（避免 Drawer 过窄）

### 5.2 全屏发布页 `/candidates/confirm/:candidateId`

**布局（D4）**：

```text
┌──────────────────────┬──────────────────────────────┐
│ 左栏 (~45%)           │ 右栏 (~55%)                   │
│ 来源链 Descriptions   │ Tabs: [ 编辑 ] [ 发布 ]       │
│ 正文 pre-wrap         │                              │
│ （长文可折叠）         │ 编辑 Tab：Form 同 Drawer 字段  │
│                      │ 发布 Tab：                     │
│                      │  - Select confirm_as (7+ignore)│
│                      │  - 动态字段（见 5.3）          │
│                      │  - searchable / usage_hint     │
│                      │  - review_comment            │
│                      │  [ 确认发布 ] [ 忽略 ]         │
└──────────────────────┴──────────────────────────────┘
```

- 发布成功 → message + 可选跳转正式对象只读页（KU list）或返回列表
- 发布失败 → 展示 `last_publish_error` + 重试按钮（同页）

### 5.3 confirm_as 动态发布字段

| confirm_as | 额外必填/选填 |
|------------|----------------|
| ku | knowledge_type, product_category_ids, chapter_taxonomy_id, searchable |
| wiki | wiki_type（可选）, 同上 |
| template_chapter | template_id, parent_chapter_id（可选）, chapter_taxonomy_id |
| manual_asset | asset_type, valid_from/to（可选）, storage_path（文件型） |
| chapter_pattern | pattern_id（若来自 mining）或内嵌创建字段 |
| product_category | category_code, parent_id（可选） |
| ignore | review_comment |

### 5.4 批量确认（D3）

1. Table 多选 ≥1 条 pending
2. **Modal** 策略：
   - 「统一发布为 KU」（弹 secondary 字段：knowledge_type、默认分类）
   - 「全部忽略」
   - 「逐条沿用建议类型」（各条 candidate_type → confirm_as 映射）
3. 提交 `POST /batch/confirm`
4. **Result Drawer**：表格 candidate_id | status | error | 操作（重试 → 全屏 confirm 页）
5. 写 audit `batch_confirm` + batch_id

### 5.5 合并 / 拆分

- **合并 Modal**：选 target（当前行或指定）+ sources 多选 + 合并后 title/content
- **拆分 Modal**：动态 Form.List（每段 title/content/candidate_type）
- 完成后刷新列表；来源项 status=merged

### 5.6 操作日志

- 列表页 Tab 或子路由 `/candidates/audit`
- 筛选：candidate_id、import_id、batch_id、action、时间
- 详情：展开 detail JSON

## 6. 交付切片 P0–P4

```text
P0  基建
  - migration：候选扩展字段 + 三正式表 + audit 表
  - candidate_adapter + enum 扩展
  - 路由壳：confirm/batch/audit 注册；全屏页空壳
  - inactive KB 写 403（与 Epic 0–3 一致）

P1  单条闭环（7 类型 + ignore）
  - candidate_publish_validator + 7 publishers + 幂等
  - PATCH /confirm /retry-publish
  - CandidateConfirmPage 两栏 Tab 全流程
  - Drawer 轻编辑 + 跳转发布
  - KU/Wiki/ManualAsset 只读 GET（验收来源链）
  - 契约 + integration：单条 publish 全类型

P2  治理效率
  - merge / split API + Modal
  - batch confirm/reject + Modal + Result Drawer
  - 列表 ProTable 筛选 + 多选

P3  审计与 polish
  - candidate-audit-logs API + Audit Tab
  - 失败重试 UX、空态、错误码文案
  - quickstart 场景 1–9 全绿

P4  横切
  - 性能：列表 P95 < 500ms；batch 50 条 < 30s
  - 检索隔离负向测试
  - Vitest：ConfirmPage + Batch Result Drawer
```

**MVP 验收线**：P3 完成 = 用户可完成 spec 全部用户故事（含 7 类型、批量、审计）。

## 7. 数据与迁移要点

详见 `specs/006-candidate-confirm-workbench/data-model.md`。Brainstorming 强调：

- `candidate_id` UNIQUE on formal tables（幂等）
- `lineage JSON` 记录 merge/split，不物理删候选行
- `chapter_pattern` 发布：优先 UPDATE 既有 `status=candidate` 行（Epic 3 挖掘产出）
- `template_chapter` 发布：stub 通道 MUST 带 `template_id`；INSERT 新章节 `status=published`

## 8. 错误处理

| 场景 | 行为 |
|------|------|
| 校验失败 | 422 + 字段 errors；不写库；audit `publish_failed` |
| 并发发布 | 409 `PUBLISH_IN_PROGRESS`（行级 lock 或 status 闸门） |
| partial failure | 正式对象已建、候选未更新 → retry 仅 PATCH 候选 + audit |
| 已发布重复 confirm | 200 幂等 + `idempotent: true` |
| 合并含非 pending | 409 `MERGE_SOURCE_NOT_PENDING` |
| 废弃 taxonomy/category | 422 `DEPRECATED_TAXONOMY` / `INVALID_PRODUCT_CATEGORY` |
| batch 部分失败 | 200 + results[] 逐条；成功项不回滚 |

## 9. 测试策略

| 层级 | 范围 |
|------|------|
| unit | `candidate_publish_validator`、各 publisher 映射、adapter ID 解析 |
| contract | PATCH/confirm/merge/split/batch/audit 契约（httpx） |
| integration | document + template 双通道 publish；幂等；batch partial fail |
| e2e manual | quickstart 场景 1–9 |
| UI | Vitest：ConfirmPage Tab 切换、confirm_as 动态字段、Batch Result Drawer |

## 10. 与 Spec Kit 制品关系

| 制品 | 本设计增量 |
|------|------------|
| spec.md | 无范围变更；UX/切片补充 |
| plan.md | 文件路径与 P0–P4 对齐本设计 §6 |
| research.md | R9 UI 细化为 §5 |
| contracts/* | 与 §4 API 一致 |

## 11. 明确不做

- 检索实现（Epic 5）
- 生成辅助（Epic 6）
- stub → 主表一次性迁移
- 双人审核 / 角色权限
- 向量索引

## 12. 下一步

1. 用户审阅本 design.md 并批准  
2. 运行 `/speckit-tasks` 生成 `tasks.md`（任务按 P0–P4 排序）  
3. Superpowers TDD 实现

---

**Decision log (brainstorming)**

- 2026-06-14 D1: 混合 UX (C)
- 2026-06-14 D2: MVP 全量 7 confirm_as（用户修订，原推荐 P1 仅 ku/wiki/template_chapter/ignore）
- 2026-06-14 D3: 批量 Modal + Result Drawer (C)
- 2026-06-14 D4: 全屏两栏 Tab 布局 (C)
- 2026-06-14 Delivery: 分层竖切 P0–P4 (方案 ③)
