# Tasks: Epic 5 目录级检索与模块建议

**Input**: Design documents from `/specs/007-outline-retrieval-module-suggestion/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md；Epic 0–4 已交付

**Tests**: 遵循 `.specify/memory/constitution.md` TDD — 每 Story 先写失败测试再实现

**Organization**: 按用户故事分组；Foundational 对应 plan Phase A；US1/US3/US2 为 P1 核心路径

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: pgvector 环境与路由壳，不阻塞 migration

- [ ] T001 Switch Postgres image to `pgvector/pgvector:pg15` in `docker-compose.yml`
- [ ] T002 Register Epic 5 route modules (`retrieval`, `module_suggestions`, `retrieval_feedback`, `retrieval_eval`) in `backend/src/main.py`
- [ ] T003 [P] Add route `/retrieval-optimization` and menu entry in `frontend/src/App.tsx`
- [ ] T004 [P] Create empty page shell `frontend/src/pages/RetrievalOptimizationCenter/index.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: migration、检索模型、索引与 trace 基建；**阻塞所有用户故事**

**⚠️ CRITICAL**: Phase 3+ 不得开始，直到本 Phase checkpoint 通过

- [ ] T005 Create Alembic migration `backend/alembic/versions/*_epic5_retrieval.py`（`CREATE EXTENSION vector` + 8 张新表 + 索引/GIN/pgvector 索引）
- [ ] T006 [P] Create `RetrievalIndexEntry` model in `backend/src/models/retrieval_index_entry.py`
- [ ] T007 [P] Create `RetrievalTrace` model in `backend/src/models/retrieval_trace.py`
- [ ] T008 [P] Create `RetrievalFeedback` model in `backend/src/models/retrieval_feedback.py`
- [ ] T009 [P] Create `RetrievalStrategyVersion` model in `backend/src/models/retrieval_strategy_version.py`
- [ ] T010 [P] Create `RetrievalEvalSet` model in `backend/src/models/retrieval_eval_set.py`
- [ ] T011 [P] Create `RetrievalEvalCase` model in `backend/src/models/retrieval_eval_case.py`
- [ ] T012 [P] Create `RetrievalEvalRun` model in `backend/src/models/retrieval_eval_run.py`
- [ ] T013 [P] Create `ModuleAssemblySuggestion` model in `backend/src/models/module_assembly_suggestion.py`
- [ ] T014 Register Epic 5 models in `backend/src/models/__init__.py`
- [ ] T015 Define `RetrievalRequest`, `KnowledgePackItem`, enums in `backend/src/schemas/retrieval.py`
- [ ] T016 Implement `retrieval_trace_service.py` in `backend/src/services/retrieval/trace/retrieval_trace_service.py`
- [ ] T017 Implement `title_normalizer.py` in `backend/src/services/retrieval/title_normalizer.py`
- [ ] T018 Implement `embedding_client.py` with env-config + degrade path in `backend/src/services/retrieval/indexing/embedding_client.py`
- [ ] T019 Implement `index_builder.py` UPSERT/deprecate in `backend/src/services/retrieval/indexing/index_builder.py`
- [ ] T020 Implement default strategy seed helper per kb in `backend/src/services/retrieval/strategy_seed.py`
- [ ] T021 Hook `index_builder` into `ku_publisher.py` and other Epic 4 publishers in `backend/src/services/publishers/`
- [ ] T022 [P] Unit test title normalization in `backend/tests/unit/test_title_normalizer.py`

**Checkpoint**: migration 可执行；默认策略版本可 seed；发布 KU 触发索引 UPSERT

---

## Phase 3: User Story 1 — 基于目标目录检索历史结构与章节模板 (Priority: P1) 🎯 MVP 入口

**Goal**: 目录级结构匹配，返回 Bid Outline / Template Chapter / Chapter Pattern + match_score、coverage_rate、score_detail

**Independent Test**: `POST /retrieval/directory-match` 带产品分类与 outline_nodes → 响应含评分与命中原因；不适用分类素材不出现

### Tests for User Story 1

- [ ] T023 [P] [US1] Contract test directory-match scores in `backend/tests/contract/test_retrieval_directory_match.py`
- [ ] T024 [P] [US1] Unit test `MatchScoreCalculator` weights in `backend/tests/unit/test_match_score_calculator.py`

### Implementation for User Story 1

- [ ] T025 [P] [US1] Implement `structure_recall.py` in `backend/src/services/retrieval/recall/structure_recall.py`
- [ ] T026 [US1] Implement `match_score_calculator.py` in `backend/src/services/retrieval/match_score_calculator.py`
- [ ] T027 [US1] Implement `knowledge_pack_builder.py` in `backend/src/services/retrieval/knowledge_pack_builder.py`
- [ ] T028 [US1] Implement directory-match leg in `backend/src/services/retrieval/retrieval_service.py`
- [ ] T029 [US1] Add `POST /directory-match` in `backend/src/api/routes/retrieval.py`
- [ ] T030 [US1] Wire trace write on directory-match via `retrieval_trace_service.py`

**Checkpoint**: US1 可独立演示目录匹配 API + trace_id

---

## Phase 4: User Story 3 — 诊断目标目录缺失章节 (Priority: P1)

**Goal**: 基于 Chapter Pattern 频次阈值诊断缺失章节，与 directory_match 一致展示

**Independent Test**: 目标目录缺高频 Pattern 时 `missing_chapters` 非空；阈值默认 ≥3 或 ≥30%

### Tests for User Story 3

- [ ] T031 [P] [US3] Unit test gap thresholds in `backend/tests/unit/test_chapter_gap_diagnoser.py`
- [ ] T032 [P] [US3] Contract test `missing_chapters` in directory-match response in `backend/tests/contract/test_retrieval_directory_match.py`

### Implementation for User Story 3

- [ ] T033 [US3] Implement `chapter_gap_diagnoser.py` in `backend/src/services/retrieval/chapter_gap_diagnoser.py`
- [ ] T034 [US3] Integrate `missing_chapters` + strategy `gap_threshold` into directory-match in `backend/src/services/retrieval/retrieval_service.py`

**Checkpoint**: US1 + US3 目录匹配含 coverage 与缺失章节诊断

---

## Phase 5: User Story 2 — 获取模块组织建议并覆盖招标约束 (Priority: P1)

**Goal**: Module Assembly Suggestion 无 LLM 编排；招标优先；冲突 risk_flags；持久化 suggestion_id

**Independent Test**: `POST /module-suggestions` → module_suggestions 含 match_score、score_point_coverage、rejection_risks；模板冲突时 risk_flags 非空且不静默采用

### Tests for User Story 2

- [ ] T035 [P] [US2] Contract test module suggestion response shape in `backend/tests/contract/test_module_suggestion.py`
- [ ] T036 [US2] Integration test template conflict `risk_flags` in `backend/tests/integration/test_module_suggestion_conflict.py`

### Implementation for User Story 2

- [ ] T037 [P] [US2] Implement `conflict_detector.py` in `backend/src/services/retrieval/ranking/conflict_detector.py`
- [ ] T038 [US2] Implement `module_suggestion_service.py` in `backend/src/services/retrieval/module_suggestion/module_suggestion_service.py`
- [ ] T039 [US2] Add `POST /` and `GET /{suggestion_id}` in `backend/src/api/routes/module_suggestions.py`
- [ ] T040 [US2] Persist rows to `module_assembly_suggestions` with trace_id linkage in `module_suggestion_service.py`

**Checkpoint**: **核心 MVP** — 目录匹配 + 缺失诊断 + 模块建议可端到端演示（P95 目标待 Polish 压测）

---

## Phase 6: User Story 4 — 多类型知识检索与可配置检索上下文 (Priority: P2)

**Goal**: 统一 `POST /retrieval/search`；intent 差异化召回；Knowledge Pack 扩展字段；trace 全记录

**Independent Test**: knowledge_lookup 带 product_category 过滤 → items 含 score、score_detail、hit_reason；pending 候选不出现在结果

### Tests for User Story 4

- [ ] T041 [P] [US4] Contract test search + intents in `backend/tests/contract/test_retrieval_search.py`
- [ ] T042 [P] [US4] Contract test trace GET in `backend/tests/contract/test_retrieval_traces.py`
- [ ] T043 [P] [US4] Integration test candidate isolation in `backend/tests/integration/test_retrieval_isolation.py`

### Implementation for User Story 4

- [ ] T044 [P] [US4] Implement `metadata_recall.py` in `backend/src/services/retrieval/recall/metadata_recall.py`
- [ ] T045 [P] [US4] Implement `keyword_recall.py` (tsvector) in `backend/src/services/retrieval/recall/keyword_recall.py`
- [ ] T046 [P] [US4] Implement `vector_recall.py` (pgvector) in `backend/src/services/retrieval/recall/vector_recall.py`
- [ ] T047 [US4] Implement `fusion_ranker.py` in `backend/src/services/retrieval/ranking/fusion_ranker.py`
- [ ] T048 [US4] Implement `retrieval_pipeline.py` in `backend/src/services/retrieval/retrieval_pipeline.py`
- [ ] T049 [US4] Implement full `search()` in `backend/src/services/retrieval/retrieval_service.py`
- [ ] T050 [US4] Add `POST /search`, `GET /traces`, `GET /traces/{trace_id}` in `backend/src/api/routes/retrieval.py`
- [ ] T051 [US4] Add `POST /index/rebuild` in `backend/src/api/routes/retrieval.py`

**Checkpoint**: US4 统一检索与 trace 查询可独立验收

---

## Phase 7: User Story 5 — 提交检索反馈以优化召回 (Priority: P2)

**Goal**: 反馈与 trace 关联；漏召回可附期望结果；可晋升为评测用例（pending）

**Independent Test**: POST feedback → feedback_id；GET trace 可关联；false_negative 缺期望返回 422

### Tests for User Story 5

- [ ] T052 [P] [US5] Contract test feedback types in `backend/tests/contract/test_retrieval_feedback.py`

### Implementation for User Story 5

- [ ] T053 [US5] Implement `retrieval_feedback_service.py` in `backend/src/services/retrieval/feedback/retrieval_feedback_service.py`
- [ ] T054 [US5] Add `POST /feedback` and `GET /feedback` in `backend/src/api/routes/retrieval_feedback.py`
- [ ] T055 [US5] Add `POST /feedback/{feedback_id}/promote-to-eval-case` in `backend/src/api/routes/retrieval_feedback.py`

**Checkpoint**: US5 反馈闭环可独立演示

---

## Phase 8: User Story 6 — 评测集管理与检索策略版本对比 (Priority: P2)

**Goal**: 评测集/用例 CRUD；人工 confirm 门禁；双策略 metrics 对比

**Independent Test**: 两 strategy_version 在同一 eval_set 上 run → metrics + comparison_metrics

### Tests for User Story 6

- [ ] T056 [P] [US6] Unit test Recall@K/NDCG in `backend/tests/unit/test_eval_metrics.py`
- [ ] T057 [P] [US6] Contract test eval run + strategy activate in `backend/tests/contract/test_retrieval_eval.py`

### Implementation for User Story 6

- [ ] T058 [US6] Implement `metrics.py` in `backend/src/services/retrieval/eval/metrics.py`
- [ ] T059 [US6] Implement `eval_runner.py` in `backend/src/services/retrieval/eval/eval_runner.py`
- [ ] T060 [US6] Add eval set/case CRUD + confirm/reject in `backend/src/api/routes/retrieval_eval.py`
- [ ] T061 [US6] Add strategy version CRUD + activate in `backend/src/api/routes/retrieval_eval.py`
- [ ] T062 [US6] Add `POST /eval/runs` and `GET /eval/runs/{eval_run_id}` in `backend/src/api/routes/retrieval_eval.py`

**Checkpoint**: US6 策略对比可独立验收

---

## Phase 9: User Story 7 — 目录中心与检索优化中心管理 (Priority: P3)

**Goal**: OutlineCenter 目录相似度 + 模块建议向导；RetrievalOptimizationCenter 全功能

**Independent Test**: UI 发起 directory-match 见评分；检索优化中心查看 trace、提交反馈、管理评测集

### Implementation for User Story 7

- [ ] T063 [P] [US7] Add API client `frontend/src/services/retrieval.ts`
- [ ] T064 [P] [US7] Add API client `frontend/src/services/moduleSuggestions.ts`
- [ ] T065 [P] [US7] Add API client `frontend/src/services/retrievalEval.ts`
- [ ] T066 [US7] Implement `OutlineSimilarityDrawer.tsx` in `frontend/src/pages/OutlineCenter/OutlineSimilarityDrawer.tsx`
- [ ] T067 [US7] Implement `ModuleSuggestionWizard.tsx` in `frontend/src/pages/OutlineCenter/ModuleSuggestionWizard.tsx`
- [ ] T068 [US7] Wire similarity + wizard actions in `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx`
- [ ] T069 [US7] Implement trace list in `frontend/src/pages/RetrievalOptimizationCenter/index.tsx`
- [ ] T070 [P] [US7] Implement `TraceDetailDrawer.tsx` in `frontend/src/pages/RetrievalOptimizationCenter/TraceDetailDrawer.tsx`
- [ ] T071 [P] [US7] Implement `EvalSetPanel.tsx` in `frontend/src/pages/RetrievalOptimizationCenter/EvalSetPanel.tsx`
- [ ] T072 [P] [US7] Implement `StrategyVersionPanel.tsx` in `frontend/src/pages/RetrievalOptimizationCenter/StrategyVersionPanel.tsx`
- [ ] T073 [P] [US7] Implement `FeedbackPanel.tsx` in `frontend/src/pages/RetrievalOptimizationCenter/FeedbackPanel.tsx`

**Checkpoint**: spec 全部 7 个用户故事可在 UI + API 独立验收

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: quickstart 全场景、性能、Epic 6 衔接

- [ ] T074 Implement Epic 5 quickstart integration flow in `backend/tests/integration/test_epic5_quickstart_flow.py`
- [ ] T075 [P] Add module suggestion P95 benchmark in `backend/tests/integration/test_module_suggestion_performance.py`
- [ ] T076 Run quickstart scenarios 0–7 from `specs/007-outline-retrieval-module-suggestion/quickstart.md` and fix gaps
- [ ] T077 [P] Batch pytest `-k "retrieval or module_suggestion or eval"` green in `backend/tests/`
- [ ] T078 Document Epic 6 consumption note for `GET /module-suggestions/{id}` in `specs/007-outline-retrieval-module-suggestion/contracts/module-suggestion-api.md`（若实现与契约一致则仅核对）

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 Setup → Phase 2 Foundational (BLOCKS ALL) → US1 → US3 → US2 → US4 → US5 → US6 → US7 → Polish
```

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Foundational | 目录结构召回 + match_score |
| US3 | US1 | 缺失章节写入 directory-match 响应 |
| US2 | US1 + US3 | 模块建议复用匹配与 gap 诊断 |
| US4 | Foundational + US1（结构腿可选） | 统一 search 管线 |
| US5 | US4（需 trace_id） | 反馈绑定 trace |
| US6 | US4 + US5 | 评测跑检索；反馈转用例 |
| US7 | US1–US6 API 就绪 | 纯前端集成 |

### Parallel Opportunities

- **Phase 2**: T006–T013 八模型并行；T022 与 T016–T019 可并行
- **US1**: T023–T025 测试与 T025 structure_recall 可并行
- **US2**: T037 conflict_detector 与 T035 测试可并行
- **US4**: T044–T046 三路 recall 并行；T041–T043 契约测试并行
- **US7**: T063–T065 三个 service 客户端并行；T070–T073 四个 Panel 并行

### Parallel Example: User Story 4 Recalls

```bash
backend/src/services/retrieval/recall/metadata_recall.py
backend/src/services/retrieval/recall/keyword_recall.py
backend/src/services/retrieval/recall/vector_recall.py
```

### Parallel Example: User Story 7 Panels

```bash
frontend/src/pages/RetrievalOptimizationCenter/TraceDetailDrawer.tsx
frontend/src/pages/RetrievalOptimizationCenter/EvalSetPanel.tsx
frontend/src/pages/RetrievalOptimizationCenter/StrategyVersionPanel.tsx
frontend/src/pages/RetrievalOptimizationCenter/FeedbackPanel.tsx
```

---

## Implementation Strategy

### MVP First（推荐停点）

1. Phase 1–2：基建（pgvector + 索引 + trace）  
2. Phase 3–5：US1 + US3 + **US2（模块建议）**  
3. **STOP & VALIDATE**：quickstart 场景 2–3 + 模块建议 API  
4. 再叠加 US4–US7

### Incremental Delivery

| 切片 | Tasks | 可演示 |
|------|-------|--------|
| P0 基建 | T001–T022 | migration + 索引钩子 |
| P1 目录 | T023–T034 | directory-match + 缺失章节 |
| P1 建议 | T035–T040 | module-suggestions API |
| P2 检索 | T041–T051 | 统一 search + trace |
| P2 闭环 | T052–T062 | 反馈 + 评测对比 |
| P3 UI | T063–T073 | 管理后台 |
| P4 收尾 | T074–T078 | quickstart 全绿 |

### Parallel Team Strategy

- Dev A：Foundational + retrieval backend（T005–T051）  
- Dev B：模块建议 + conflict（T035–T040）  
- Dev C：OutlineCenter UI（T066–T068）  
- Dev D：RetrievalOptimizationCenter（T069–T073）  
- 汇合：integration + quickstart（T074, T076）

---

## Notes

- 仅索引 `status=published` 且 `searchable=true` 的正式资产；候选永不入索引  
- 每个 Task：Red → Green → Refactor；先跑对应 test 确认 FAIL  
- 单任务避免同文件冲突（尤其 `retrieval_service.py`、`retrieval.py`）  
- Out of scope：章节草稿生成（Epic 6）、完整招标解析、复杂自动学习  
- embedding 未配置时向量腿降级，trace 须记录 `vector_disabled_reason`

---

## Task Summary

| Phase | Tasks | Count |
|-------|-------|-------|
| Setup | T001–T004 | 4 |
| Foundational | T005–T022 | 18 |
| US1 | T023–T030 | 8 |
| US3 | T031–T034 | 4 |
| US2 | T035–T040 | 6 |
| US4 | T041–T051 | 11 |
| US5 | T052–T055 | 4 |
| US6 | T056–T062 | 7 |
| US7 | T063–T073 | 11 |
| Polish | T074–T078 | 5 |
| **Total** | **T001–T078** | **78** |

**Suggested MVP scope**: Phase 1–2 + US1 + US3 + US2（T001–T040，共 40 tasks）  
**Full spec acceptance**: T001–T073（至 US7）  
**Production-ready**: T001–T078（含 quickstart + 性能探针）
