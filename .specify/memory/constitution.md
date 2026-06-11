<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.0.0 (validation pass; no principle changes)
Modified principles: None
Added sections: None
Removed sections: None
Templates requiring updates:
  - .specify/templates/plan-template.md ✅ verified (G1–G6 aligned)
  - .specify/templates/spec-template.md ✅ verified (no changes required)
  - .specify/templates/tasks-template.md ✅ updated (TDD aligned with constitution)
  - .cursor/rules/specify-rules.mdc ✅ verified
  - README.md ✅ verified (no changes required)
  - .cursorrules ✅ verified (references constitution pipeline)
Follow-up TODOs: None
-->

# tender_knowledge Constitution

## Core Principles

### I. Spec-Driven Delivery

所有非平凡功能 MUST 遵循 Spec Kit 流水线：`/speckit-specify` → `/speckit-plan` →
`/speckit-tasks` → 实现。在 `tasks.md` 生成并完成 Constitution Check 之前，MUST NOT
开始编写实现代码。

产品范围以 `docs/总需求.md`（V3.0）为权威来源；Epic 拆分以 `docs/epics/` 为准。
功能规格 MUST 可追溯到对应 Epic 与用户故事，且独立可测试、独立可交付。

**Rationale**: 本仓库当前以需求与研发协作为主；Spec Kit 流水线确保设计与实现一致，
避免跳过规格直接编码。

### II. Knowledge Asset First

系统 MUST 以知识资产（Knowledge Unit、Wiki、Template、Manual Asset、Chapter Pattern）
为核心消费对象，而非原始文件或导入批次。

单文件导入（Imported File / Document）是生产路径的起点，但检索、推荐、生成辅助
MUST 面向已治理、已发布、可追溯的知识对象。未确认候选知识 MUST NOT 作为正式检索
或生成输入。

**Rationale**: V3.0 产品定位是"真实标书素材资产平台"，资产治理质量决定平台价值。

### III. Human Confirmation Gate (NON-NEGOTIABLE)

实际标书、模板文件解析产生的 Candidate Knowledge MUST 经人工确认后方可发布为
正式 KU / Wiki / Template Chapter / Manual Asset / Chapter Pattern。

自动识别结果（文件用途、产品分类、章节类型）MAY 作为建议，但人工覆盖结果 MUST
优先于机器结果。人工修正后的 Document Tree、Bid Outline、Template Chapter MUST NOT
被后续自动重解析直接覆盖；只能生成待确认差异。

**Rationale**: 标书知识涉及合规与业务准确性；人工确认是 V2.0/V3.0 继承的核心治理原则。

### IV. Chapter-First & Full Traceability

知识组织、检索过滤、模块组织建议、生成辅助 MUST 以章节结构（Document Tree、
Bid Outline、Template Chapter、Chapter Taxonomy）为边界。

任何知识对象、推荐结果、生成草稿 MUST 可追溯到来源文件、目录节点、导入记录、
版本与操作审计。服务层 MUST 记录结构化 trace（如 retrieval_trace、module suggestion
trace）。

**Rationale**: 标书场景以章节为最小治理与生成单元；全链路可追溯支撑审核与评测闭环。

### V. Retrieval Before Generation

平台 MUST 优先保证检索准确、召回完整、结果可解释，再提供 AI 生成辅助。

目录级模块组织建议（不含 LLM）P95 MUST 小于 2 秒；检索策略 MUST 支持 intent、
产品分类、章节分类等过滤。生成辅助 MUST 以外部招标约束（Tender Requirement Context）
为最高优先级；模板库仅提供小模块组织建议与历史表达参考，MUST NOT 覆盖招标结构要求。

**Rationale**: "先找得准、找得全、可追溯，再生成"是 V3.0 继承原则；错误生成成本
高于错误检索。

## Technology & Architecture Constraints

### 四层资产体系

实现 MUST 对齐 V3.0 资产分层，不得绕过层级直接暴露原始文件：

```text
来源层：Imported File / Document / Manual Asset
  ↓
结构层：Document Tree / Bid Outline / Template Library / Template Chapter
  ↓
知识层：Knowledge Unit / Wiki / Chapter Pattern / Product Category
  ↓
服务层：Retrieval / Recommend / Module Suggestion / Generation Assist / Open API
```

外部招标约束（Tender Requirement Context）不属于知识库内部资产，但在服务层调用时
MUST 作为最高优先级输入。

### V3.0-MVP 范围约束

- 导入模型：单文件导入；MUST NOT 在 MVP 中实现目录/文件夹批量导入。
- 分类底座：Epic 0（Product Category + Chapter Taxonomy）MUST 在文件导入 Epic 之前可用。
- 权限：V3.0 暂缓角色权限设计；敏感文件仍 MUST 支持加密存储与审计日志。
- 数据生命周期：已发布对象 MUST NOT 物理删除，只能废弃（soft deprecate）。
- LLM：用于解析、分类、提取、推荐；人工负责确认与治理。LLM 输出 MUST 进入候选区
  或待确认差异，不得静默入库。

### 非功能基线

- 可观测性：文件导入、用途识别、模板解析、候选生成、人工确认、检索与模块建议
  MUST 有可关联 trace_id 的结构化日志。
- 安全：未确认候选知识 MUST NOT 通过 API 或检索泄露；导入、确认、发布、废弃、
  检索反馈 MUST 有审计日志。
- 可恢复性：File Import、模板解析、Candidate Knowledge 发布 MUST 支持失败重试，
  且失败不得破坏已存在的源文件记录。

## Development Workflow & Quality Gates

### Spec Kit 流水线

1. **ARCHITECTURE**: 读取本 constitution 与 `docs/总需求.md` 确认约束。
2. **THINKING**: 运行 `/speckit-specify` 与 `/speckit-plan` 生成 Markdown 制品；
   此阶段 MUST NOT 编写实现代码。
3. **EXECUTION**: `tasks.md` 生成后，交由 Superpowers 按任务执行。
4. **TDD LOOP**: 每个任务遵循 Write Test → Implement → Refactor；测试 MUST 在实现前
   编写并先失败（Red-Green-Refactor）。

### Plan 阶段 Constitution Check

`plan.md` 的 Constitution Check 章节 MUST 验证：

| Gate | 验证项 |
|------|--------|
| G1 Spec-Driven | 规格已映射 Epic/用户故事；无跳过 spec/plan 的直接编码 |
| G2 Knowledge Asset | 设计以 KU/Wiki/Template 等资产为输出，非仅文件存储 |
| G3 Human Confirmation | 自动产出路径包含 Candidate → 人工确认 → 发布 |
| G4 Chapter & Trace | 章节边界与 trace/audit 设计已明确 |
| G5 Retrieval First | 检索/推荐接口与性能目标已定义；生成辅助不优先于检索 |
| G6 MVP Scope | 未引入文件夹批量导入等 MVP 外能力 |

违反原则 MUST 在 plan.md 的 Complexity Tracking 表中说明理由与被拒绝的更简单方案。

### Epic 交付顺序

默认遵循 README 中的 Epic 依赖：

```text
Epic 0 分类底座 → Epic 1 来源导入 → Epic 2/3 可并行 → Epic 4 → Epic 5 → Epic 6
```

跨 Epic 功能 MUST 在 spec/plan 中显式声明依赖，不得隐式假设前置 Epic 已完成。

## Governance

- 本 constitution 优先于 `.cursorrules`、README 及临时开发约定；冲突时以本文件为准。
- 修订 MUST 通过 `/speckit-constitution` 执行，并同步更新受影响的 Spec Kit 模板与
  `.cursor/rules/specify-rules.mdc`。
- 版本号遵循语义化版本：MAJOR（原则删除或重新定义）、MINOR（新增原则或实质性扩展）、
  PATCH（措辞澄清、非语义修正）。
- 所有 PR / 功能评审 MUST 核对 Constitution Check（G1–G6）；复杂度例外 MUST 有
  书面 justification。
- 运行时开发指引：`docs/总需求.md`、`docs/epics/`、`.cursorrules`、当前 feature 的
  `specs/<feature>/plan.md`。

**Version**: 1.0.0 | **Ratified**: 2026-06-11 | **Last Amended**: 2026-06-11
