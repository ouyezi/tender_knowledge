# Implementation Plan: Epic 6 生成辅助升级

**Branch**: `008-generation-assist-upgrade` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-generation-assist-upgrade/spec.md`

## Summary

在 Epic 0–5 已发布知识资产与模块组织建议基础上，实现 **外部招标约束持久化、模块建议采纳确认、
模板变量填写、条件章节评估、多源输入优先级编排、LLM 章节草稿生成、逐段引用绑定、
Generation Snapshot 审计、生成任务异步状态与接受/废弃/重新生成工作流**。

复用 FastAPI + PostgreSQL + React 单体；扩展 `llm_client` 与 Epic 5 的 `ModuleSuggestionService`、
`ConflictDetector`、`KnowledgePackBuilder`；新增 `services/generation/` 子系统；前端扩展
OutlineCenter 模块建议向导 → 章节草稿生成面板。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15 + pgvector;
React 18, Ant Design 5, Vite, @ant-design/pro-components

**Reuse from Epic 0–5**:

- 正式资产：KU、Wiki、Manual Asset、Template Chapter、Template Variable、Template Rule
- Epic 5：`ModuleAssemblySuggestion`、`RetrievalTrace`、`ConflictDetector`、
  `KnowledgePackBuilder`、`POST/GET /module-suggestions`
- Epic 2：`TemplateVariable`（`{{key}}` 占位符）、`TemplateRule`（条件章节）
- `llm_client.chat_completion` + `is_llm_available` 降级模式
- `get_trace_id()` / `AuditMiddleware` / `BackgroundTasks` 异步任务模式（同 file_import）

**Storage**: PostgreSQL 15；新增 `tender_requirement_contexts`、`generation_tasks`、
`chapter_drafts`、`generation_snapshots`；扩展 `module_assembly_suggestions` 采纳状态字段

**Testing**: pytest + httpx（契约/集成）；Vitest（ChapterDraftPanel UI）；fixtures 含
招标约束 + 模块建议 + 已发布 KU/Template Chapter seed；LLM 路径 mock + 可选 live 探针

**Target Platform**: Linux/macOS 开发；Docker Compose；生产 Linux 容器

**Project Type**: web-service（backend API + admin frontend）

**Performance Goals**: 章节草稿生成典型章节端到端 ≤ 3 分钟（SC-001，含 LLM）；生成任务
状态查询 P95 < 200ms；快照详情查询 P95 < 500ms；变量校验同步路径 P95 < 300ms

**Constraints**: 招标约束优先于模板；未确认候选不得作生成输入；LLM 未配置时生成 API
返回明确降级错误；快照 append-only 不可变；生成不自动发布为正式 KU/Wiki

**Scale/Scope**: 单 KB 并发生成任务 ~10；快照保留 180 天（可配置）；Epic 6 不实现
Template Instance、完整招标解析、多章节联动生成

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | Epic 6 spec + plan 后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 生成消费已发布 KU/Wiki/Template；草稿为辅助输出非静默入库 | ✅ | ✅ |
| G3 | Human Confirmation Gate | 模块建议采纳 + 草稿接受/废弃由人工驱动；LLM 输出不入正式区 | ✅ | ✅ |
| G4 | Chapter-First & Traceability | 章节边界生成 + Generation Snapshot + 逐段 citation | ✅ | ✅ |
| G5 | Retrieval Before Generation | 消费 Epic 5 检索/建议；InputPriorityResolver 招标优先 | ✅ | ✅ |
| G6 | MVP Scope | 无完整招标解析、无 Template Instance、无文件夹导入 | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/008-generation-assist-upgrade/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── tender-requirement-api.md
│   └── generation-api.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/routes/
│   │   ├── tender_requirements.py       # 招标约束 CRUD
│   │   ├── generation.py                # 草稿生成、任务、快照、接受/废弃
│   │   └── module_suggestions.py        # 扩展 PATCH 采纳状态
│   ├── models/
│   │   ├── tender_requirement_context.py
│   │   ├── generation_task.py
│   │   ├── chapter_draft.py
│   │   ├── generation_snapshot.py
│   │   └── module_assembly_suggestion.py  # 扩展 status/adopted 字段
│   ├── services/generation/
│   │   ├── generation_service.py           # 编排入口
│   │   ├── input_priority_resolver.py      # 废标项>评分点>...优先级
│   │   ├── variable_resolver.py            # {{key}} 校验与替换
│   │   ├── conditional_chapter_evaluator.py  # TemplateRule 评估
│   │   ├── prompt_builder.py               # 结构化 prompt + 版本号
│   │   ├── citation_binder.py              # 逐段引用绑定
│   │   ├── snapshot_writer.py              # 不可变快照写入
│   │   └── compliance_checker.py           # Manual Asset 合规消费
│   ├── schemas/
│   │   └── generation.py
│   └── main.py                             # 注册新路由
├── tests/
│   ├── contract/test_tender_requirement_*.py
│   ├── contract/test_generation_*.py
│   ├── integration/test_epic6_quickstart_flow.py
│   ├── integration/test_generation_conflict_priority.py
│   └── unit/test_input_priority_resolver.py
└── alembic/versions/xxxx_epic6_generation.py

frontend/
├── src/
│   ├── pages/
│   │   └── OutlineCenter/
│   │       ├── ModuleSuggestionWizard.tsx    # 扩展：采纳确认
│   │       ├── TenderRequirementForm.tsx     # 招标约束录入
│   │       ├── VariableFillPanel.tsx         # 变量填写
│   │       └── ChapterDraftPanel.tsx         # 草稿预览/引用/接受废弃
│   ├── services/
│   │   ├── tenderRequirements.ts
│   │   └── generation.ts
│   └── App.tsx
```

**Structure Decision**: 延续 Epic 0–5 monorepo。生成子系统独立 `services/generation/`，
与 `services/retrieval/` 平级；招标约束为服务层实体非 KB 资产表。前端在 OutlineCenter
扩展向导式流程（约束 → 建议 → 变量 → 生成 → 快照），不新建独立页面。

## Complexity Tracking

> 无 Constitution 违规项；本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 Output

See [research.md](./research.md) — 招标约束持久化、FastAPI BackgroundTasks 异步生成、
InputPriorityResolver、变量简单占位符、条件章节规则评估、LLM prompt 版本化、
Citation Binder、Generation Snapshot 不可变模型、模块建议采纳扩展均已决议。

## Phase 1 Output

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Tender Requirement API | [contracts/tender-requirement-api.md](./contracts/tender-requirement-api.md) |
| Generation API | [contracts/generation-api.md](./contracts/generation-api.md) |
| Validation guide | [quickstart.md](./quickstart.md) |

## Implementation Phases (for tasks.md)

### Phase A — 基础设施（阻塞后续）

1. Alembic migration（新表 + module_assembly_suggestions 扩展字段）
2. SQLAlchemy models + Pydantic schemas
3. `TenderRequirementService` CRUD
4. 默认 `prompt_config_versions` seed（generation prompt v1）

### Phase B — 输入编排（P1）

5. `VariableResolver`（必填校验 + `{{key}}` 替换）
6. `ConditionalChapterEvaluator`（复用 TemplateRule）
7. `InputPriorityResolver` + `ComplianceChecker`
8. 扩展 `ModuleSuggestionService` 采纳状态 PATCH

### Phase C — 生成核心（P1）

9. `PromptBuilder` + `CitationBinder`
10. `GenerationService.generate_draft`（BackgroundTasks）
11. `SnapshotWriter` 不可变写入
12. `POST /generation/drafts` + `GET /generation/tasks/{id}`

### Phase D — 快照与工作流（P1–P2）

13. `GET /generation/snapshots/{id}` + 列表 API
14. 重新生成 / 接受 / 废弃 API
15. 草稿段落 → 快照 citation 跳转数据模型

### Phase E — 前端（P1–P2）

16. TenderRequirementForm + ModuleSuggestionWizard 采纳步骤
17. VariableFillPanel + ChapterDraftPanel
18. Epic 6 quickstart 集成测试 + LLM mock 契约测试

### Phase F — 质量与衔接

19. 冲突优先级集成测试（招标 vs 模板）
20. 变量拦截 100% 契约测试
21. Constitution G4/G5 追溯字段验收清单

## Post-Design Constitution Re-check

| Gate | Post-Design Evidence |
|------|---------------------|
| G1 | spec.md + plan.md + contracts 完整 |
| G2 | 生成输入仅已发布资产；草稿不自动 publish |
| G3 | 采纳/接受/废弃人工门控；LLM 输出仅 chapter_draft |
| G4 | generation_snapshot + paragraph citations + trace 摘要 |
| G5 | InputPriorityResolver；消费 module-suggestions + knowledge pack |
| G6 | Out of Scope 在 spec + plan + contracts 显式列出 |

**All gates pass.**
