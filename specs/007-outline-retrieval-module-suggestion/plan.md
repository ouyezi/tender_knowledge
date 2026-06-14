# Implementation Plan: Epic 5 目录级检索与模块建议

**Branch**: `007-outline-retrieval-module-suggestion` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-outline-retrieval-module-suggestion/spec.md`

## Summary

在 Epic 0–4 已发布知识资产基础上，实现 **目录级检索、历史模块推荐、缺失章节诊断、
模块组织建议（无 LLM）、retrieval_trace 全链路追溯、检索反馈与评测闭环、策略版本管理**。
复用 FastAPI + PostgreSQL + React 单体；引入 **pgvector** 与统一 `retrieval_index_entries`
多态索引；混合召回管线（元数据 + tsvector 关键词 + 向量 + 结构匹配）+ 可解释
match_score/coverage_rate；扩展 OutlineCenter 目录相似度；新增 RetrievalOptimizationCenter
管理后台。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15 + pgvector,
psycopg; React 18, Ant Design 5, Vite, @ant-design/pro-components

**Reuse from Epic 0–4**:

- 正式资产表：KU、Wiki、Manual Asset、Template Chapter、Bid Outline/Node、Chapter Pattern
- Epic 0 分类校验、`chapter_taxonomy_service.search_taxonomies`
- Epic 3 Bid Outline API 与 `OutlineCenter` 前端
- Epic 4 `searchable` 门控与候选隔离测试模式
- `get_trace_id()` / audit 中间件模式

**Storage**: PostgreSQL 15（pgvector 扩展）；新增检索索引、trace、反馈、评测、策略版本、
模块建议持久化表；`STORAGE_ROOT` 只读（Manual Asset 元数据过滤）

**Testing**: pytest + httpx（契约/集成）；Vitest（RetrievalOptimizationCenter、
OutlineCenter 相似度 UI）；fixtures 含已发布 KU + Outline + Pattern seed；
P95 模块建议路径性能用例

**Target Platform**: Linux/macOS 开发；Docker Compose（`pgvector/pgvector:pg15`）；
生产 Linux 容器

**Project Type**: web-service（backend API + admin frontend）

**Performance Goals**: 模块组织建议（无 LLM）P95 < 2s（SC-001）；检索 search P95 < 1s
（典型 KB ~200 索引条目）；trace 详情查询 P95 < 500ms；评测 run 异步、50 用例 < 60s

**Constraints**: 仅索引已发布且 searchable 资产；招标约束优先于模板；无章节草稿生成；
无复杂自动学习；embedding API 可配置且可降级；策略版本可对比

**Scale/Scope**: 单 KB 索引条目 ~5k；trace 保留 90 天（可配置）；评测集 ~500 用例；
Epic 5 不实现 Epic 6 生成辅助

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | Epic 5 spec + plan 后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 检索/建议面向 KU/Wiki/Template 等已发布资产 | ✅ | ✅ |
| G3 | Human Confirmation Gate | 不索引候选；反馈转评测用例须人工 confirm | ✅ | ✅ |
| G4 | Chapter-First & Traceability | 章节边界检索 + retrieval_trace + suggestion 来源链 | ✅ | ✅ |
| G5 | Retrieval Before Generation | 本 Epic 仅检索/建议；招标约束优先；无 LLM 草稿 | ✅ | ✅ |
| G6 | MVP Scope | 无文件夹导入、无自动学习、无完整招标解析 | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/007-outline-retrieval-module-suggestion/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── retrieval-api.md
│   ├── module-suggestion-api.md
│   ├── retrieval-feedback-api.md
│   └── retrieval-eval-api.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/routes/
│   │   ├── retrieval.py              # search, directory-match, traces, index/rebuild
│   │   ├── module_suggestions.py     # POST/GET module suggestions
│   │   ├── retrieval_feedback.py     # feedback CRUD + promote-to-eval
│   │   └── retrieval_eval.py         # eval sets/cases/runs + strategies
│   ├── models/
│   │   ├── retrieval_index_entry.py
│   │   ├── retrieval_trace.py
│   │   ├── retrieval_feedback.py
│   │   ├── retrieval_strategy_version.py
│   │   ├── retrieval_eval_set.py
│   │   ├── retrieval_eval_case.py
│   │   ├── retrieval_eval_run.py
│   │   └── module_assembly_suggestion.py
│   ├── services/retrieval/
│   │   ├── retrieval_service.py          # 统一 search 入口
│   │   ├── retrieval_pipeline.py
│   │   ├── match_score_calculator.py
│   │   ├── chapter_gap_diagnoser.py
│   │   ├── title_normalizer.py
│   │   ├── knowledge_pack_builder.py
│   │   ├── recall/
│   │   │   ├── metadata_recall.py
│   │   │   ├── keyword_recall.py         # tsvector
│   │   │   ├── vector_recall.py          # pgvector
│   │   │   └── structure_recall.py       # outline/template/pattern
│   │   ├── ranking/
│   │   │   ├── fusion_ranker.py
│   │   │   └── conflict_detector.py      # 招标 vs 模板
│   │   ├── module_suggestion/
│   │   │   └── module_suggestion_service.py
│   │   ├── indexing/
│   │   │   ├── index_builder.py
│   │   │   └── embedding_client.py
│   │   ├── trace/
│   │   │   └── retrieval_trace_service.py
│   │   ├── feedback/
│   │   │   └── retrieval_feedback_service.py
│   │   └── eval/
│   │       ├── eval_runner.py
│   │       └── metrics.py
│   ├── schemas/
│   │   └── retrieval.py                  # RetrievalRequest, KnowledgePackItem, ...
│   └── main.py                             # 注册新路由
├── tests/
│   ├── contract/test_retrieval_*.py
│   ├── contract/test_module_suggestion_*.py
│   ├── integration/test_epic5_quickstart_flow.py
│   ├── integration/test_retrieval_isolation.py
│   └── unit/test_match_score_calculator.py
└── alembic/versions/xxxx_epic5_retrieval.py

frontend/
├── src/
│   ├── pages/
│   │   ├── OutlineCenter/
│   │   │   ├── OutlineSimilarityDrawer.tsx   # 目录相似度
│   │   │   └── ModuleSuggestionWizard.tsx    # 模块建议入口
│   │   └── RetrievalOptimizationCenter/
│   │       ├── index.tsx                     # trace 列表
│   │       ├── TraceDetailDrawer.tsx
│   │       ├── EvalSetPanel.tsx
│   │       ├── StrategyVersionPanel.tsx
│   │       └── FeedbackPanel.tsx
│   ├── services/
│   │   ├── retrieval.ts
│   │   ├── moduleSuggestions.ts
│   │   └── retrievalEval.ts
│   └── App.tsx                               # /retrieval-optimization 路由
docker-compose.yml                            # postgres → pgvector/pgvector:pg15
```

**Structure Decision**: 延续 Epic 0–4 monorepo。检索子系统按 `services/retrieval/` 分模块，
避免单文件膨胀。索引构建挂接 Epic 4 publish 钩子 + 独立 rebuild API。前端扩展 OutlineCenter
而非重复 Bid Outline CRUD。

## Complexity Tracking

> 无 Constitution 违规项；本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 Output

See [research.md](./research.md) — 混合检索管线、pgvector+tsvector、embedding 可配置降级、
match_score 规则评分、模块建议编排、trace/反馈/评测模型、Knowledge Pack 扩展、UI 划分、
测试策略均已决议。

## Phase 1 Output

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Retrieval API | [contracts/retrieval-api.md](./contracts/retrieval-api.md) |
| Module Suggestion API | [contracts/module-suggestion-api.md](./contracts/module-suggestion-api.md) |
| Feedback API | [contracts/retrieval-feedback-api.md](./contracts/retrieval-feedback-api.md) |
| Eval & Strategy API | [contracts/retrieval-eval-api.md](./contracts/retrieval-eval-api.md) |
| Validation guide | [quickstart.md](./quickstart.md) |

## Implementation Phases (for tasks.md)

### Phase A — 基础设施（阻塞后续）

1. Docker pgvector 镜像 + Alembic migration（扩展 + 新表）
2. SQLAlchemy models + Pydantic schemas
3. 默认 `retrieval_strategy_versions` seed（per kb）
4. `EmbeddingClient` + `IndexBuilder` + publish 钩子

### Phase B — 检索核心（P1）

5. Keyword + metadata + structure recall
6. Vector recall（embedding 配置时）
7. `RetrievalService.search` + trace 写入
8. `MatchScoreCalculator` + `ChapterGapDiagnoser`
9. `POST /retrieval/search` + `POST /retrieval/directory-match` + trace GET

### Phase C — 模块建议（P1）

10. `ModuleSuggestionService` + conflict detector
11. `module_assembly_suggestions` 持久化
12. `POST /module-suggestions` API

### Phase D — 反馈与评测（P2）

13. Feedback API + promote-to-eval-case
14. Eval set/case CRUD + confirm 门禁
15. `RetrievalEvalRunner` + metrics + compare API
16. Strategy version CRUD + activate

### Phase E — 管理后台（P2–P3）

17. OutlineCenter 目录相似度 + 模块建议向导
18. RetrievalOptimizationCenter 全页
19. Epic 5 quickstart 集成测试 + 性能探针

### Phase F — Epic 6 衔接

20. Knowledge Pack 字段稳定契约文档化（contracts 已含）
21. `GET /module-suggestions/{id}` 供下游拉取

## Post-Design Constitution Re-check

| Gate | Post-Design Evidence |
|------|---------------------|
| G1 | spec.md + plan.md + contracts 完整 |
| G2 | retrieval_index_entries 仅正式资产；Knowledge Pack 扩展 |
| G3 | 索引排除候选；eval case confirm 门禁 |
| G4 | trace_id 贯穿 search/suggestion/feedback；score_detail 可追溯 |
| G5 | 无生成 API；招标优先 conflict_detector；P95 目标写入 SC-001 |
| G6 | Out of Scope 在 spec + plan 显式列出 |

**All gates pass.**
