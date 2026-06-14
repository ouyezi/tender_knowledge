# Design: Epic 6 生成辅助 — LLM 管线与引用绑定

**Date**: 2026-06-14  
**Status**: Approved  
**Feature spec**: `specs/008-generation-assist-upgrade/spec.md`  
**Implementation plan (Spec Kit)**: `specs/008-generation-assist-upgrade/plan.md`  
**Spec Kit tasks**: `specs/008-generation-assist-upgrade/tasks.md` (T001–T072)  
**Epic source**: `docs/epics/epic6-生成辅助升级.md`

## 1. 背景与目标

Epic 0–5 已交付分类底座、已发布知识资产、目录级检索与 **Module Assembly Suggestion**（无 LLM）。
Epic 6 在人工确认招标约束与模块建议后，提供 **可追溯的章节草稿辅助生成**。

本设计在 Spec Kit `research.md` / `plan.md` 基础上，经 brainstorming 确认以下实现前技术基线：

- 分阶段管线 + 薄编排器（方案 B）
- Source Catalog + `ref_id` 结构化 LLM 输出（方案 4c）
- 按 `task_id` 精准执行的 BackgroundTasks（非全局 pending 扫描）
- 输入六层优先级 + ConflictDetector 预检/后检双阶段
- CitationBinder 段落级引用绑定与 snapshot 不可变审计

**Out of scope**：Template Instance、完整招标解析、多章节联动、草稿自动 publish 为正式 KU/Wiki。

## 2. Brainstorming 决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 整体架构 | **方案 B**：`services/generation/` 分阶段组件 + `GenerationService` 薄编排 |
| D2 | LLM 输出 | **方案 4c**：Prompt 内嵌 Source Catalog；LLM 仅返回 `source_ref_ids` |
| D3 | 异步任务 | **`run_generation_task_in_new_session(task_id)`**；按 task 执行，非扫全局队列 |
| D4 | 冲突处理 | **预检**（不进 prompt L6）+ **后检**（citation 含冲突 id → conflict_hints） |
| D5 | Citation | **CitationBinder** 查 catalog 填完整 citation；段级至少 1 引用 |
| D6 | MVP 顺序 | Foundational → US1 → US2 → US3 → US4 → US5 → US6 → UI |

## 3. 实现路径对比（Brainstorming）

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| A. 单体编排 | 单文件内联全部逻辑 | 文件少 | 难测、难维护 |
| **B. 分阶段管线（采用）** | 8 个 focused service + 薄 orchestrator | TDD 友好；与 Epic 5 风格一致 | 文件数略多 |
| C. 两阶段生成+事后检索挂引用 | LLM 出正文后再检索绑 citation | 表面来源齐 | 非 LLM 实际依据；难满足 SC-002 |

## 4. 架构

### 4.1 端到端数据流

```text
POST /generation/drafts
  → 同步门控（VariableResolver / suggestion adopted / LLM available）
  → INSERT generation_tasks(status=pending)
  → BackgroundTasks.add_task(run_generation_task_in_new_session, task_id)
  → 202 { task_id }

run_generation_task_in_new_session(task_id):
  → SessionLocal()
  → status=running
  → GenerationService.run_task(task_id)
       → VariableResolver（已预检，运行时使用 resolved values）
       → ConditionalChapterEvaluator
       → InputPriorityResolver → ResolvedGenerationContext
       → ComplianceChecker
       → PromptBuilder（generation-v1.0.0 + source_catalog）
       → llm_client.chat_completion → JSON paragraphs
       → CitationBinder
       → ConflictDetector 后检
       → SnapshotWriter（append-only）
       → ChapterDraft persist
  → status=completed | failed
  → db.close()
```

### 4.2 组件职责

| 组件 | 路径（计划） | 职责 |
|------|-------------|------|
| `TenderRequirementService` | `services/generation/tender_requirement_service.py` | 招标约束 CRUD（服务层，非 KB 资产） |
| `VariableResolver` | `services/generation/variable_resolver.py` | 必填校验、`{{key}}` 替换 |
| `ConditionalChapterEvaluator` | `services/generation/conditional_chapter_evaluator.py` | 复用 Epic 2 `TemplateRule` |
| `InputPriorityResolver` | `services/generation/input_priority_resolver.py` | 六层上下文 + source_catalog 构建 |
| `ComplianceChecker` | `services/generation/compliance_checker.py` | 消费 manual_asset_compliance |
| `PromptBuilder` | `services/generation/prompt_builder.py` | 版本化 prompt 组装 |
| `CitationBinder` | `services/generation/citation_binder.py` | ref_id → 完整 citation |
| `SnapshotWriter` | `services/generation/snapshot_writer.py` | 不可变 Generation Snapshot |
| `GenerationService` | `services/generation/generation_service.py` | 编排 + 状态更新 |
| `ConflictDetector` | `services/retrieval/ranking/conflict_detector.py` | **复用** Epic 5 |

### 4.3 与 Epic 5 衔接

| Epic 5 产出 | Epic 6 消费方式 |
|-------------|----------------|
| `ModuleAssemblySuggestion` | 须 `adopted`（或 confirm_adoption）；`knowledge_pack_snapshot` |
| `RetrievalTrace` | snapshot 写入 `retrieval_trace_summary` |
| `ConflictDetector` | 预检过滤 L6 template hints；后检 citation |
| `KnowledgePackBuilder` 字段 | 纳入 L5 knowledge_pack |

## 5. 输入优先级与冲突

### 5.1 六层 Prompt 注入顺序

```text
L1 rejection_clauses     — MANDATORY，不得违反
L2 score_points          — MUST address
L3 outline_structure       — 标书结构要求
L4 user_selections       — 条件章节手工选择
L5 knowledge_pack        — KU/Wiki 摘要
L6 template_hints        — REFERENCE ONLY，不得覆盖 L1–L3
```

`InputPriorityResolver` 输出 `ResolvedGenerationContext`：

- `layers`: 六层文本块
- `source_catalog`: 稳定 ref 列表（见 §6.2）
- `conflict_pre_flags`: 预检 risk_flags

### 5.2 ConflictDetector 双阶段

| 阶段 | 时机 | 行为 |
|------|------|------|
| **预检** | 组装 L6 前 | 冲突 template_chapter_id **排除**出 L6；写入 risk_flags |
| **后检** | CitationBinder 后 | 若 citation 含冲突 template id → `conflict_hints`（高 severity）；**不自动删正文** |

MVP 沿用 Epic 5 token 规则（`原厂授权`、`排他` 等）；不引入 NLP 扩词。

## 6. LLM 输出与 Prompt 版本化

### 6.1 Prompt 版本

- 表 `prompt_config_versions` 或 seed：`generation-v1.0.0`
- Snapshot 记录：`prompt_version`, `model`, `provider`

### 6.2 Source Catalog ID 约定

| ref_id 前缀 | 含义 |
|-------------|------|
| `SRC-NNN` | catalog 中 KU / Wiki / Template Chapter / Manual Asset |
| `TREQ-RC-*` | 废标项条目 |
| `TREQ-SP-*` | 评分点条目 |
| `VAR-{key}` | 变量取值 |

Catalog 条目示例：

```json
{
  "ref_id": "SRC-001",
  "type": "ku",
  "object_id": "uuid",
  "title": "历史技术方案-架构",
  "excerpt": "分层架构包括接入层、服务层……"
}
```

### 6.3 LLM 期望 JSON Schema（v1.0.0）

```json
{
  "paragraphs": [
    {
      "text": "本项目总体架构采用分层设计……",
      "source_ref_ids": ["SRC-001", "TREQ-SP-0"],
      "addresses_score_points": ["SP-0"]
    }
  ],
  "generation_notes": "可选：缺失素材说明"
}
```

### 6.4 解析与容错

1. 剥离 markdown code fence（若存在）
2. `json.loads` → 失败则 **一次** repair 调用（小 max_tokens）
3. 仍失败 → `task.status=failed`, `error_code=PARSE_FAILED`
4. 未知 `source_ref_id` → CitationBinder 记 `orphan_ref` warning，不阻断完成

### 6.5 llm_client 使用

- 复用 `chat_completion`；`GenerationService` 内封装 JSON 解析
- `max_tokens` 默认 **4096**
- `is_llm_available()` false → 同步返回 `503 LLM_UNAVAILABLE`，**不创建 running task**

## 7. 异步任务

### 7.1 与现有 BackgroundTasks 模式差异

Epic 2/3 使用 `run_*_pending()` 扫描全局队列。Epic 6 **必须**传入 `task_id`：

```python
background_tasks.add_task(run_generation_task_in_new_session, task_id)
```

避免与 template_parse 队列混淆；每请求独立 lifecycle。

### 7.2 状态机

```text
pending → running → completed
                 └→ failed
```

| error_code | 含义 |
|------------|------|
| `LLM_UNAVAILABLE` | 未配置 LLM（同步预检或运行时发现） |
| `GENERATION_FAILED` | LLM 调用失败 / 超时 |
| `PARSE_FAILED` | JSON 解析失败（含 repair 后） |

### 7.3 失败与重试规则

- 失败 **不写入** Generation Snapshot 或 ChapterDraft
- `request_snapshot` 保留于 task 行供排查
- 重试：`POST /drafts` 或 `POST /drafts/{id}/regenerate` → **新 task_id**、新 snapshot
- 超时：复用 `settings.llm_request_timeout_sec`

## 8. Citation Binder

### 8.1 输入 / 输出

**输入**：LLM paragraphs + `source_catalog` + variable map + tender layers  
**输出**：契约 `chapter_drafts.paragraphs[]`：

```json
{
  "paragraph_index": 0,
  "text": "……",
  "citations": [
    {
      "source_type": "ku",
      "source_id": "uuid",
      "source_label": "历史技术方案-架构",
      "excerpt": "分层架构包括……",
      "ref_id": "SRC-001"
    }
  ]
}
```

### 8.2 绑定规则

1. `ref_id` 查 catalog → 填充 citation 字段
2. 每段 **至少 1** citation；空 `source_ref_ids` 时绑 `TREQ-SP-*` 或 tender 兜底
3. 变量：`text` 二次 `{{key}}` replace；补 `VAR-{key}` citation
4. `used_ku_ids` / `used_wiki_ids` / … 从 citations 去重 → snapshot

## 9. Generation Snapshot（不可变）

- **append-only**：仅 INSERT，无业务 UPDATE
- 每次成功生成一条 snapshot；`chapter_drafts.snapshot_id` FK
- accept/discard 只改 `chapter_drafts.outcome_status` / `is_active`
- 必含字段（FR-010）：requirement_context 引用、suggestion 引用、target_outline_node、
  used_*_ids、variable_inputs、retrieval_trace_summary、prompt_version、result_version

## 10. 测试策略

| 层级 | 覆盖 |
|------|------|
| Unit | `InputPriorityResolver`, `VariableResolver`, `CitationBinder`, `ConditionalChapterEvaluator` |
| Contract | tender-requirements CRUD, drafts/tasks, snapshots, adoption PATCH, `MISSING_REQUIRED_VARIABLES` |
| Integration | `test_epic6_quickstart_flow.py`（mock LLM 固定 JSON） |
| Integration | `test_generation_conflict_priority.py`（预检 + 后检） |
| CI | patch `llm_client.chat_completion`；`LLM_LIVE_TEST=1` 可选 live 探针 |

**Red-Green 顺序**：先写失败测试 → 实现 → refactor（Constitution TDD）。

## 11. MVP 实现顺序（对齐 tasks.md）

```text
Phase 2 Foundational (T005–T016)
  → US1 招标约束 + adoption (T017–T022)
  → US2 VariableResolver (T023–T027)
  → US3 生成管线 + BackgroundTasks (T028–T041)  ← 核心停点
  → US4 snapshot GET (T042–T046)
  → US5 条件章节 (T047–T051)
  → US6 工作流 (T052–T057)
  → UI (T058–T066)
  → Polish (T067–T072)
```

**推荐 MVP 停点**：T001–T041 + quickstart 场景 1–4 + mock 集成测试通过。

## 12. 错误码与 API 对齐

与 `specs/008-generation-assist-upgrade/contracts/generation-api.md` 一致：

| HTTP | code | 场景 |
|------|------|------|
| 422 | `MISSING_REQUIRED_VARIABLES` | 同步预检 |
| 422 | `SUGGESTION_NOT_ADOPTED` | suggestion 非 adopted |
| 422 | `ASSET_NOT_PUBLISHED` | 引用未发布资产 |
| 503 | `LLM_UNAVAILABLE` | LLM 未配置 |
| 202 | — | task 已创建 pending |

## 13. Spec Self-Review（2026-06-14）

| 检查项 | 结果 |
|--------|------|
| TBD / TODO 占位 | 无 |
| 与 spec.md / plan.md 矛盾 | 无；本设计细化 research R3–R4 |
| 范围过大需拆分 | 否；单 Epic 6 管线 |
| 歧义需求 | Source Catalog ref 规则已固定；后检不删正文已明确 |
| Constitution G3/G4/G5 | 人工 adoption/accept；snapshot 不可变；招标优先 |

---

**Approved by user**: 2026-06-14（brainstorming 会话确认）
