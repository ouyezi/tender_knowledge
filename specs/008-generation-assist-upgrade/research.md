# Research: Epic 6 生成辅助升级

**Date**: 2026-06-14  
**Feature**: `specs/008-generation-assist-upgrade`

## R1 — Tender Requirement Context 持久化模型

### Decision

新增服务层表 `tender_requirement_contexts`，**不属于 KB 内部知识资产**，但可持久化供
多次模块建议与生成引用。字段覆盖 spec FR-001；通过独立 API 创建/更新/查询；
`requirement_context_id` 写入 `module_assembly_suggestions` 与 `generation_snapshots`。

招标约束 MAY 以内联 JSON 快照形式冗余存储于 suggestion/snapshot（便于审计复现），
但以 `requirement_context_id` 为权威引用。

### Rationale

- 对齐总需求 §11.1：平台消费外部/人工录入结构化约束，非完整解析系统。
- Generation Snapshot 需 requirement_context 引用（FR-010）。
- 与 Constitution「外部招标约束非 KB 资产」一致：独立表、不参与 retrieval_index。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 仅请求体内联、不持久化 | 无法跨会话复现；快照审计链断裂 |
| 存入 KB metadata 表 | 混淆资产分层；违反四层体系 |
| 完整招标文件解析入库 | Out of Scope；Epic 6 不建设 |

---

## R2 — 异步生成任务模式

### Decision

采用 **FastAPI `BackgroundTasks` + `generation_tasks` 状态表**（与 file_import、
template_parse 一致），状态枚举：`pending` → `running` → `completed` | `failed`。

- `POST /generation/drafts` 同步校验输入（变量必填、资产 published），创建 task 行，
  返回 `task_id`；后台执行 LLM 生成。
- 客户端轮询 `GET /generation/tasks/{task_id}` 直至终态。
- 失败保留 `error_message`；不写入不完整 snapshot（edge case：partial debug 可选
  `debug_trace` JSON，不暴露为正式草稿）。

### Rationale

- 仓库已有 BackgroundTasks 模式，无 Celery/Redis 依赖。
- SC-001 允许 ≤3 分钟；异步避免 HTTP 超时。
- 并发任务独立追踪（spec edge case）。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 同步阻塞 HTTP 至 LLM 完成 | 易超时；前端体验差 |
| 引入 Celery + Redis | MVP 运维复杂度不必要 |
| WebSocket 推送 | 当前前端无 WS 基础设施 |

---

## R3 — LLM 生成管线与 Prompt 版本化

### Decision

`GenerationService` 管线：

```text
GenerationRequest
  → VariableResolver.validate（阻断必填缺失）
  → ConditionalChapterEvaluator.evaluate
  → InputPriorityResolver.build_context（招标优先排序上下文块）
  → ComplianceChecker.filter_manual_assets
  → PromptBuilder.build（versioned template v1.0.0）
  → llm_client.chat_completion（JSON 结构化输出：paragraphs + source_hints）
  → CitationBinder.bind（段落 ↔ KU/Wiki/Template/约束/变量）
  → ConflictDetector 二次校验（模板引用 vs 废标项）
  → SnapshotWriter.write（append-only）
  → ChapterDraft persist
```

- **Prompt 版本**：`prompt_config_versions` 表或 config JSON seed；snapshot 记录
  `prompt_version`。
- **LLM 不可用**：`is_llm_available()` false 时 task 立即 `failed`，错误码
  `LLM_UNAVAILABLE`；trace 记录原因。
- **输出格式**：要求 LLM 返回 JSON `{ "paragraphs": [{ "text", "source_refs": [...] }] }`，
  便于 citation 绑定与测试 mock。

### Rationale

- 复用现有 `llm_client`；与 chunk_classification 等服务一致。
- 结构化输出降低 citation 解析失败率，满足 SC-002。
- Prompt 版本化满足 FR-010 与 Constitution 可观测性。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 纯文本 LLM 输出 + 事后 regex 引用 | citation 不可靠；难测 |
| 多轮 Agent 工具调用 | 复杂度高；超出 Epic 6 范围 |
| 模板字符串零 LLM 拼接 | 无法满足「辅助生成」业务价值 |

---

## R4 — 输入优先级解析（InputPriorityResolver）

### Decision

在 prompt 组装前，将输入上下文块按固定优先级 **分层注入** system/user prompt：

```text
Layer 1: rejection_clauses（废标项，MUST 遵守）
Layer 2: score_points（评分点，MUST 覆盖说明）
Layer 3: outline_structure（标书结构要求）
Layer 4: user_selections（用户采纳的模块/条件章节手工选择）
Layer 5: knowledge_pack（KU/Wiki 内容摘要）
Layer 6: template_chapter_hints（模板库参考，标注「仅供参考」）
```

冲突时低层内容在 prompt 中显式标注「不得覆盖 Layer 1–3」；`ConflictDetector`
输出写入 `conflict_hints` 字段展示给用户。

### Rationale

- 直接实现 spec FR-007 与 Constitution G5。
- 可单元测试（`test_input_priority_resolver.py`）无需 LLM。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 仅依赖 LLM system prompt 说明优先级 | 不可控；SC-007 难保证 |
| 生成后 diff 招标约束 | 事后修复成本高 |

---

## R5 — 模板变量：简单占位符替换

### Decision

- 复用 Epic 2 `TemplateVariable`（`variable_key`、`required`、`default_value`、
  `placeholder_pattern` 默认 `{{key}}`）。
- `VariableResolver`：
  - 合并用户提交值与默认值；
  - 必填缺失 → HTTP 422 `MISSING_REQUIRED_VARIABLES`（同步阻断，不创建 task）；
  - 生成前对 Template Chapter 参考文本做占位符替换预览；
  - 最终取值写入 snapshot `variable_inputs` JSON。
- **不支持**复杂表达式（总需求 D9）；`value_type` 仅做基础校验（string/number/date）。

### Rationale

- Epic 2 模型已存在；避免重复建模。
- SC-005 要求 100% 拦截与快照一致。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| Jinja2 模板引擎 | 违反 D9 简单占位符原则 |
| 生成后全局 find-replace | 无法保证段落级 citation 一致 |

---

## R6 — 条件章节评估

### Decision

`ConditionalChapterEvaluator` 读取 Epic 2 `TemplateRule`（`rule_type=conditional|product_match`），
结合招标约束关键词、产品分类、客户类型、Manual Asset 资质存在性，输出
`suggested_chapter_enables[]`（建议启用列表 + 理由 + risk_flags）。

- 用户手工选择存储于 `generation_requests.user_chapter_selections` JSON。
- 评估结果 **仅建议**；`InputPriorityResolver` Layer 4 采纳用户最终选择。

### Rationale

- 复用已有 TemplateRule 模型与 Epic 2 API。
- 满足 US5 / FR-005；不重复实现规则引擎。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 新建独立 conditional_chapter 表 | 与 TemplateRule 重复 |
| LLM 推断条件章节 | 不可解释；难审计 |

---

## R7 — Generation Snapshot 不可变审计

### Decision

- 表 `generation_snapshots` **append-only**（无 UPDATE 业务路径；仅 INSERT）。
- 每次成功生成一条 snapshot；`chapter_drafts.snapshot_id` FK 关联。
- 重新生成产生 **新** snapshot + 新 draft；旧记录保留。
- 字段含 spec FR-010 全集 + `generation_trace_id`（关联 retrieval trace 摘要）。

### Rationale

- Constitution G4 全链路追溯；合规审核要求。
- 接受/废弃仅更新 `chapter_drafts.outcome_status`，不修改 snapshot。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 快照存 object storage 文件 | 查询与关联复杂 |
| 覆盖式更新同一 snapshot | 审计链断裂 |

---

## R8 — Module Assembly Suggestion 采纳扩展

### Decision

扩展 Epic 5 `module_assembly_suggestions` 表：

- 新增 `requirement_context_id`（FK，nullable 兼容历史数据）
- 新增 `status` enum：`draft` | `adopted` | `rejected`
- 新增 `adopted_by`、`adopted_at`、`reason`（用户备注，optional）

新增 `PATCH /module-suggestions/{id}/adoption` API；生成请求 MUST 引用
`adopted` 状态 suggestion 或允许 `draft` + 内联确认（quickstart 场景）。

### Rationale

- Epic 5 模型缺采纳状态；Epic 6 US1/US3 要求人工确认后生成。
- 最小扩展，不重构 ModuleSuggestionService 核心召回逻辑。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 独立 adoption 关联表 | 过度建模 |
| 生成时忽略 suggestion 状态 | 违反 Human Confirmation Gate |

---

## R9 — Manual Asset 合规校验消费

### Decision

- 初版 `ComplianceChecker` 消费请求体 `manual_asset_compliance[]`
  （`asset_id`, `status: pass|fail|missing`, `message`）。
- 合规结果来源：上游人工标注或 Epic 并行能力；Epic 6 **不实现**完整合规引擎。
- `fail|missing` 资产：不出现在 LLM 参考上下文；输出 `missing_material_hints`。

### Rationale

- spec Assumptions 明确合规结果由并行能力提供。
- 避免 Epic 6 范围膨胀。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| Epic 6 内置资质 OCR 校验 | Out of Scope |
| 忽略合规输入 | 违反 US3 验收场景 |

---

## R10 — 前端工作流划分

### Decision

在 **OutlineCenter** 扩展向导步骤（非新顶级路由）：

1. 录入/选择 Tender Requirement Context
2. 生成并查看 Module Suggestion → 采纳/拒绝
3. VariableFillPanel
4. 发起生成 + 轮询任务状态
5. ChapterDraftPanel（段落引用、冲突提示、接受/废弃/重新生成）
6. Snapshot 详情 Drawer

### Rationale

- 与 Epic 5 ModuleSuggestionWizard 自然衔接（US 19.5 用户旅程）。
- 避免碎片化页面。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 独立 /generation-assist 顶级页 | 与目录中心上下文割裂 |
| 仅 API 无 UI | 不符合现有 admin 产品形态 |

---

## R11 — 测试策略

### Decision

| 层级 | 覆盖 |
|------|------|
| Unit | InputPriorityResolver、VariableResolver、ConditionalChapterEvaluator |
| Contract | tender-requirement CRUD、generation drafts/tasks/snapshots、adoption PATCH |
| Integration | epic6_quickstart_flow（mock LLM）；generation_conflict_priority |
| Mock | `llm_client` patch 返回固定 JSON paragraphs |
| Optional live | 环境变量 `LLM_LIVE_TEST=1` 单用例探针 |

### Rationale

- TDD 对齐 Constitution；LLM 非确定性需 mock 保证 CI 稳定。
