# Research: Epic 4 候选知识确认工作台

**Date**: 2026-06-14  
**Feature**: `specs/006-candidate-confirm-workbench`

## R1 — 双源候选统一适配（document + template stub）

### Decision

保留 Epic 3 的 **复合 candidate_id** 约定（`doc_{uuid}` / `tpl_{uuid}`），在 Epic 4 写操作层
引入 `CandidateAdapter` 抽象：统一读写 `candidate_knowledges` 与 `candidate_knowledge_stubs`
两表，对外 API 形状一致。

列表/详情 API 在 Epic 3 只读基础上扩展筛选字段（`chapter_taxonomy_id`、
`suggested_product_category_ids` 包含过滤）；写 API 仅接受复合 ID。

### Rationale

- Epic 3 已实现聚合列表，前端 `CandidateCenter` 已消费该 ID 格式。
- Epic 4 spec FR-016 要求不单独建 Candidate Template Chapter 表；stub 表继续作为模板通道
  存储，Epic 4 负责确认时写入正式 Template Chapter。
- 避免大规模迁移 stub → 主表；MVP 以适配器收敛，tasks 阶段可评估长期归一。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 迁移 stub 到 candidate_knowledges | 破坏 Epic 2 解析确认链路；迁移成本高 |
| 两套独立 confirm API | 前端与审计重复；违背工作台「统一入口」 |

---

## R2 — 发布编排器（Confirm-as Publish Orchestrator）

### Decision

实现 `candidate_publish_service.publish()` 作为 **单入口编排器**，按 `confirm_as` 分发到
类型专属 publisher：

| confirm_as | 目标表/操作 |
|------------|-------------|
| ku | `knowledge_units` INSERT |
| wiki | `wikis` INSERT |
| template_chapter | `template_chapters` INSERT（stub 通道带 template_id） |
| manual_asset | `manual_assets` INSERT |
| chapter_pattern | `chapter_patterns.status` → confirmed |
| product_category | `product_categories` INSERT |
| ignore | 候选 status → rejected |

每个 publisher 在 **同一 DB 事务** 内：校验 → 创建/更新正式对象 → 回写候选
`confirmed_object_type/id` + `status=published` → 写审计。

### Rationale

- 对齐总需求 §12.2 发布映射与 Constitution G3。
- 复用 Epic 2 `template_publish_service` 的事务与 audit 模式。
- 便于幂等：编排器开头检查 `status=published` + `confirmed_object_id`。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 各类型独立 REST 端点 | 批量确认与审计难统一 |
| 异步队列发布 | MVP 过度；管理员需即时反馈 |

---

## R3 — 正式知识层新表（KU / Wiki / Manual Asset）

### Decision

Epic 4 **新建** 三张正式知识表（Epic 3 仅产出 pending 候选，未建 KU/Wiki/Manual Asset）：

- `knowledge_units`：content、summary、knowledge_type、product_category_ids、
  chapter_taxonomy_id、import_id、candidate_id、source_doc_id、source_node_id、
  bid_outline_id（nullable）、searchable、version_no、status（published/deprecated）
- `wikis`：同上简化字段 + wiki_type
- `manual_assets`：asset_type、storage_path（可空，内容型资质）、valid_from/to、
  product_category_ids、candidate_id、import_id

所有正式对象 MUST 含 `candidate_id` FK（nullable 仅允许历史回填）与 `import_id`。

### Rationale

- 总需求 §6.3 定义 KU 来源字段；Constitution 四层资产体系要求知识层实体。
- Epic 5 检索将索引这些表；Epic 4 必须先落库。
- MVP 不实现向量索引，仅 `searchable` 布尔门 + 元数据字段。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 发布到 Document Tree Node | 违反 Knowledge Asset First |
| 延迟到 Epic 5 建表 | Epic 4 无法完成发布验收 |

---

## R4 — 合并 / 拆分语义

### Decision

**合并**：

- 选择 `target_candidate_id` + `source_candidate_ids[]`（均 pending）。
- 目标候选 content/title/summary 按管理员提交或默认拼接；来源链写入
  `merge_lineage` JSON（`{merged_from: [candidate_id...]}`）。
- 来源候选 `status=merged`，`merged_into_id=target`；禁止对已发布/已忽略项合并。

**拆分**：

- 对单条 pending 候选提交 `splits[]`（title、summary、content 片段、candidate_type 建议）。
- 原候选 `status=merged`（或 `split` 子状态用 merged + lineage）；新建 N 条 pending 子候选，
  `split_from_id=原 candidate_id`，继承 import/source 链。

新增字段：`merged_into_id`、`split_from_id`、`lineage JSON`（candidate_knowledges +
candidate_knowledge_stubs 同步扩展）。

### Rationale

- Spec 要求来源不丢失；lineage JSON 比物理删行更符合「不可物理删除」原则。
- 合并后仍走单条 publish 流程，降低编排复杂度。

---

## R5 — 发布幂等与失败重试

### Decision

- 发布前检查：若 `status=published` 且 `confirmed_object_id` 非空 → 返回 **200 幂等**
  （同一 confirmed_object，不重复 INSERT）。
- 若正式对象已创建但候选状态未更新（partial failure）→ 重试仅 PATCH 候选状态 +
  审计 `publish_retry`。
- 每次 publish 请求生成/传递 `trace_id`；失败写 `last_publish_error`（text）到候选行。

### Rationale

- 满足 spec SC-005、FR-012 与 Constitution 可恢复性。
- 避免 duplicate KU 导致 Epic 5 检索污染。

---

## R6 — 候选区检索隔离

### Decision

- **不**在 Epic 4 实现检索服务；在 publish 层与现有 list API 层 enforce：
  - 所有 `status IN (pending, confirmed)` 候选 excluded from future retrieval index tables
    （Epic 5 建索引时 filter `status=published` 正式对象 only）。
- 新增契约测试：`GET /retrieval/...`（Epic 5 stub）与 confirm 前候选 ID 交叉查询 MUST 404/empty
  （Epic 4 quickstart 用 mock 或 negative test on KU list API if exists）。

Epic 4 交付 `searchable` 字段默认值：KU/Wiki 发布时可配置；Manual Asset 默认 true。

### Rationale

- Constitution G5：Epic 4 定义边界，Epic 5 消费；本 Epic 负责正式对象入库门。

---

## R7 — 审计日志模型

### Decision

新建 `candidate_confirm_audit_logs`（不混入 `actual_bid_audit_logs` / `template_audit_logs`）：

| action | 场景 |
|--------|------|
| candidate_edit | 标题/摘要/正文/分类 PATCH |
| candidate_publish | 单条发布成功 |
| candidate_publish_failed | 发布失败 |
| candidate_ignore | 忽略 |
| candidate_merge | 合并 |
| candidate_split | 拆分 |
| batch_confirm | 批量确认汇总 |
| batch_reject | 批量驳回汇总 |

字段：audit_id, kb_id, candidate_id（复合 ID 字符串）, action, operator_id, trace_id,
detail JSON, created_at。

批量操作额外写 **一条批次头** 记录 + detail 内 `items[]` 逐条结果。

### Rationale

- Spec FR-011 / SC-007 要求按 candidate_id 或批次检索。
- 独立表便于 Epic 4 工作台「操作日志」Tab，不耦合解析域日志。

---

## R8 — 扩展 candidate_type 枚举

### Decision

对齐总需求 §6.15，扩展 `CandidateKnowledgeType`：

```text
ku | wiki | template_chapter | manual_asset | chapter_pattern | product_category | ignore
```

Epic 3 当前仅 `ku | wiki | chapter_pattern | ignore`；Epic 4 migration ADD VALUE。
生成侧（Epic 2/3）可逐步补充类型；工作台 MUST 支持全部 confirm_as 映射。

### Rationale

- Epic spec FR-016 与 epic4 文档一致。
- ignore 作为类型与 confirm_as 双通道：列表筛选 + 快速驳回。

---

## R9 — 管理台 UI 范围

### Decision

升级 `frontend/src/pages/CandidateCenter/`：

- 列表：ProTable + 筛选（批次、产品分类、章节类型、候选类型、状态、来源通道）
- 详情抽屉：编辑表单 + 发布面板（confirm_as、分类、searchable、review_comment）
- 操作：合并/拆分 Modal、批量确认/驳回、操作日志 Tab

路由保持 `/candidates`；与 Epic 3 只读页 incremental 增强。

### Rationale

- Epic 3 已预留 CandidateCenter；最小 diff 升级。
- 对齐 spec SC-001/SC-002 管理员操作时长目标。

---

## R10 — 发布校验规则

### Decision

发布前统一校验（`candidate_publish_validator`）：

1. 候选 status MUST pending（或 confirmed 预填但未 published）
2. product_category_ids 全部 active（Epic 0）
3. chapter_taxonomy_id active（若 confirm_as 需要）
4. title 非空；ku/wiki 需 knowledge_type
5. 来源链：document 通道需 source_doc_id + source_node_id；template 通道需 template_id
6. template_chapter 发布需有效 parent template（来自 stub.template_id）
7. product_category 发布需 category_code 唯一性检查

校验失败 → 422 + 字段级 errors，不写库。

### Rationale

- 落实 spec FR-006 与 edge case「废弃分类不可发布」。
