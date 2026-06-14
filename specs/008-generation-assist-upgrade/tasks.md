# Tasks: Epic 6 生成辅助升级

**Input**: Design documents from `/specs/008-generation-assist-upgrade/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md；Epic 0–5 已交付

**Tests**: 遵循 `.specify/memory/constitution.md` TDD — 每 Story 先写失败测试再实现

**Organization**: 按用户故事分组；Foundational 对应 plan Phase A；US1–US4 为 P1 核心路径

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 路由注册与前端壳，不阻塞 migration

- [ ] T001 Register Epic 6 routers `tender_requirements` and `generation` in `backend/src/main.py`
- [ ] T002 [P] Create API client shell `frontend/src/services/tenderRequirements.ts`
- [ ] T003 [P] Create API client shell `frontend/src/services/generation.ts`
- [ ] T004 [P] Create component shells `TenderRequirementForm.tsx`, `VariableFillPanel.tsx`, `ChapterDraftPanel.tsx` in `frontend/src/pages/OutlineCenter/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: migration、生成模型、schemas、prompt seed；**阻塞所有用户故事**

**⚠️ CRITICAL**: Phase 3+ 不得开始，直到本 Phase checkpoint 通过

- [ ] T005 Create Alembic migration `backend/alembic/versions/*_epic6_generation.py`（4 张新表 + `module_assembly_suggestions` 扩展列 + FK/索引）
- [ ] T006 [P] Create `TenderRequirementContext` model in `backend/src/models/tender_requirement_context.py`
- [ ] T007 [P] Create `GenerationTask` model in `backend/src/models/generation_task.py`
- [ ] T008 [P] Create `ChapterDraft` model in `backend/src/models/chapter_draft.py`
- [ ] T009 [P] Create `GenerationSnapshot` model in `backend/src/models/generation_snapshot.py`
- [ ] T010 [P] Create `PromptConfigVersion` model in `backend/src/models/prompt_config_version.py`
- [ ] T011 Extend `ModuleAssemblySuggestion` with `requirement_context_id`, `status`, `adopted_by`, `adopted_at`, `adoption_reason` in `backend/src/models/module_assembly_suggestion.py`
- [ ] T012 Register Epic 6 models in `backend/src/models/__init__.py`
- [ ] T013 Define generation enums and request/response schemas in `backend/src/schemas/generation.py`
- [ ] T014 Implement default generation prompt seed `generation-v1.0.0` in `backend/src/services/generation/prompt_seed.py`
- [ ] T015 Create `backend/src/services/generation/` package with `__init__.py`
- [ ] T016 [P] Add Epic 6 fixtures（tender context、suggestion、mock LLM JSON）in `backend/tests/conftest.py`

**Checkpoint**: migration 可执行；prompt v1 seed 可加载；models 可 import

---

## Phase 3: User Story 1 — 录入外部招标约束并获取模块组织建议 (Priority: P1) 🎯 MVP 入口

**Goal**: Tender Requirement Context CRUD；模块建议关联 context；用户采纳/拒绝 suggestion

**Independent Test**: 创建招标约束 → `POST /module-suggestions` → `PATCH .../adoption` 为 `adopted`；建议含理由与 risk_flags

### Tests for User Story 1

- [ ] T017 [P] [US1] Contract test tender-requirements CRUD in `backend/tests/contract/test_tender_requirement_crud.py`
- [ ] T018 [P] [US1] Contract test suggestion adoption PATCH in `backend/tests/contract/test_module_suggestion_adoption.py`

### Implementation for User Story 1

- [ ] T019 [US1] Implement `TenderRequirementService` CRUD in `backend/src/services/generation/tender_requirement_service.py`
- [ ] T020 [US1] Add routes `POST/GET/PATCH/archive` in `backend/src/api/routes/tender_requirements.py`
- [ ] T021 [US1] Persist `requirement_context_id` and `tender_context_snapshot` on suggestion create in `backend/src/services/retrieval/module_suggestion/module_suggestion_service.py`
- [ ] T022 [US1] Add `PATCH /module-suggestions/{suggestion_id}/adoption` in `backend/src/api/routes/module_suggestions.py`

**Checkpoint**: US1 可独立演示招标约束录入 + 模块建议采纳 API

---

## Phase 4: User Story 2 — 配置模板章节变量并填写生成所需变量值 (Priority: P1)

**Goal**: 必填变量校验；`{{key}}` 占位符解析；缺必填时同步 422 阻断

**Independent Test**: 缺必填变量 `POST /generation/drafts` → 422 `MISSING_REQUIRED_VARIABLES`；补全后通过预检

### Tests for User Story 2

- [ ] T023 [P] [US2] Unit test required/default merge in `backend/tests/unit/test_variable_resolver.py`
- [ ] T024 [P] [US2] Contract test `MISSING_REQUIRED_VARIABLES` in `backend/tests/contract/test_generation_drafts_validation.py`

### Implementation for User Story 2

- [ ] T025 [US2] Implement `VariableResolver` validate + replace in `backend/src/services/generation/variable_resolver.py`
- [ ] T026 [US2] Implement `collect_variables_for_suggestion()` loading Epic 2 `TemplateVariable` in `backend/src/services/generation/variable_resolver.py`
- [ ] T027 [US2] Export sync preflight `validate_generation_variables()` for draft create in `backend/src/services/generation/variable_resolver.py`

**Checkpoint**: US2 变量校验可独立单元/契约测试，不依赖 LLM

---

## Phase 5: User Story 3 — 基于多源输入生成可追溯的章节草稿 (Priority: P1)

**Goal**: 异步生成任务；LLM 结构化段落；逐段 citation；招标优先；冲突提示

**Independent Test**: mock LLM → `POST /generation/drafts` → 轮询 `completed` → draft 每段含 citations；冲突场景 `conflict_hints` 非空

### Tests for User Story 3

- [ ] T028 [P] [US3] Unit test priority layers in `backend/tests/unit/test_input_priority_resolver.py`
- [ ] T029 [P] [US3] Unit test citation binding in `backend/tests/unit/test_citation_binder.py`
- [ ] T030 [P] [US3] Contract test drafts + task status in `backend/tests/contract/test_generation_drafts.py`
- [ ] T031 [US3] Integration test full flow with mock LLM in `backend/tests/integration/test_epic6_quickstart_flow.py`

### Implementation for User Story 3

- [ ] T032 [P] [US3] Implement `InputPriorityResolver` in `backend/src/services/generation/input_priority_resolver.py`
- [ ] T033 [P] [US3] Implement `ComplianceChecker` in `backend/src/services/generation/compliance_checker.py`
- [ ] T034 [US3] Implement `PromptBuilder` with version tag in `backend/src/services/generation/prompt_builder.py`
- [ ] T035 [US3] Implement `CitationBinder` paragraph↔source mapping in `backend/src/services/generation/citation_binder.py`
- [ ] T036 [US3] Implement append-only `SnapshotWriter` in `backend/src/services/generation/snapshot_writer.py`
- [ ] T037 [US3] Implement `GenerationService.generate_draft()` orchestration in `backend/src/services/generation/generation_service.py`
- [ ] T038 [US3] Wire `VariableResolver` + adopted suggestion gate in `backend/src/services/generation/generation_service.py`
- [ ] T039 [US3] Reuse Epic 5 `ConflictDetector` post-LLM pass in `backend/src/services/generation/generation_service.py`
- [ ] T040 [US3] Add `POST /drafts` and `GET /tasks/{task_id}` in `backend/src/api/routes/generation.py`
- [ ] T041 [US3] Dispatch `BackgroundTasks` worker for LLM generation in `backend/src/api/routes/generation.py`

**Checkpoint**: **核心 MVP** — 招标约束 + 采纳建议 + 变量 + 章节草稿生成可端到端演示（mock LLM）

---

## Phase 6: User Story 4 — 查看生成快照以审计与复现生成结果 (Priority: P1)

**Goal**: 草稿详情；快照详情与列表；段落可定位到 snapshot 输入与引用

**Independent Test**: 生成完成后 `GET /snapshots/{id}` 含 `prompt_version`、`variable_inputs`、`used_*_ids`；`GET /drafts/{id}` 段落 citations 可解析

### Tests for User Story 4

- [ ] T042 [P] [US4] Contract test snapshot + draft GET in `backend/tests/contract/test_generation_snapshots.py`

### Implementation for User Story 4

- [ ] T043 [US4] Add `GET /drafts/{draft_id}` and `GET /drafts` list in `backend/src/api/routes/generation.py`
- [ ] T044 [US4] Add `GET /snapshots/{snapshot_id}` and `GET /snapshots` list in `backend/src/api/routes/generation.py`
- [ ] T045 [US4] Persist `retrieval_trace_summary` from suggestion trace in `backend/src/services/generation/snapshot_writer.py`
- [ ] T046 [US4] Ensure `paragraphs[].citations` schema matches contract in `backend/src/schemas/generation.py`

**Checkpoint**: US4 审计链可独立查询，不依赖重新生成

---

## Phase 7: User Story 5 — 处理条件章节建议与冲突风险提示 (Priority: P2)

**Goal**: TemplateRule 条件评估；用户手工选择优先；冲突风险提示

**Independent Test**: 匹配 product_match 规则 → 建议启用列表；与废标项冲突 → risk 标记；用户 selection 写入 snapshot

### Tests for User Story 5

- [ ] T047 [P] [US5] Unit test rule evaluation in `backend/tests/unit/test_conditional_chapter_evaluator.py`
- [ ] T048 [US5] Integration test conflict priority in `backend/tests/integration/test_generation_conflict_priority.py`

### Implementation for User Story 5

- [ ] T049 [US5] Implement `ConditionalChapterEvaluator` using Epic 2 `TemplateRule` in `backend/src/services/generation/conditional_chapter_evaluator.py`
- [ ] T050 [US5] Integrate conditional suggestions into `GenerationService` input assembly in `backend/src/services/generation/generation_service.py`
- [ ] T051 [US5] Wire `user_chapter_selections` in request schema and snapshot in `backend/src/schemas/generation.py`

**Checkpoint**: US5 条件章节与冲突优先级可独立集成测试验收

---

## Phase 8: User Story 6 — 重新生成、接受或废弃章节草稿 (Priority: P2)

**Goal**: accept/discard/regenerate 工作流；版本递增；历史 snapshot 保留

**Independent Test**: accept → `outcome_status=accepted`；regenerate → 新 task + 新 snapshot；discard → `is_active=false` 且 snapshot 仍可查

### Tests for User Story 6

- [ ] T052 [P] [US6] Contract test accept/discard/regenerate in `backend/tests/contract/test_generation_workflow.py`

### Implementation for User Story 6

- [ ] T053 [US6] Add `POST /drafts/{draft_id}/accept` in `backend/src/api/routes/generation.py`
- [ ] T054 [US6] Add `POST /drafts/{draft_id}/discard` in `backend/src/api/routes/generation.py`
- [ ] T055 [US6] Add `POST /drafts/{draft_id}/regenerate` in `backend/src/api/routes/generation.py`
- [ ] T056 [US6] Implement outcome_status + is_active transitions in `backend/src/services/generation/generation_service.py`
- [ ] T057 [US6] Implement version_tag increment on regenerate in `backend/src/services/generation/generation_service.py`

**Checkpoint**: US6 草稿生命周期完整，符合 Human Confirmation Gate

---

## Phase 9: User Story 7 — OutlineCenter 生成辅助 UI (Priority: P1–P2)

**Goal**: 向导式 UI：约束 → 建议采纳 → 变量 → 生成 → 快照 → 接受/废弃

**Independent Test**: UI 可走通 quickstart 场景 1–6（LLM 配置或 mock 后端）

### Implementation for User Story 7

- [ ] T058 [P] [US1] Implement full client in `frontend/src/services/tenderRequirements.ts`
- [ ] T059 [US1] Implement `TenderRequirementForm.tsx` in `frontend/src/pages/OutlineCenter/TenderRequirementForm.tsx`
- [ ] T060 [US1] Extend adoption step in `frontend/src/pages/OutlineCenter/ModuleSuggestionWizard.tsx`
- [ ] T061 [US2] Implement `VariableFillPanel.tsx` in `frontend/src/pages/OutlineCenter/VariableFillPanel.tsx`
- [ ] T062 [US3] Implement full client with polling in `frontend/src/services/generation.ts`
- [ ] T063 [US3] Implement draft preview + citations in `frontend/src/pages/OutlineCenter/ChapterDraftPanel.tsx`
- [ ] T064 [US4] Implement `SnapshotDetailDrawer.tsx` in `frontend/src/pages/OutlineCenter/SnapshotDetailDrawer.tsx`
- [ ] T065 [US6] Wire accept/discard/regenerate actions in `frontend/src/pages/OutlineCenter/ChapterDraftPanel.tsx`
- [ ] T066 [US3] Integrate wizard steps in `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx`

**Checkpoint**: spec 全部 6 个用户故事可在 UI + API 验收

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: quickstart 全场景、Constitution 追溯验收、Epic 5 衔接核对

- [ ] T067 Run quickstart scenarios 0–7 from `specs/008-generation-assist-upgrade/quickstart.md` and fix gaps
- [ ] T068 [P] Contract test `LLM_UNAVAILABLE` when env unset in `backend/tests/contract/test_generation_drafts.py`
- [ ] T069 [P] Contract test unpublished asset rejection in `backend/tests/contract/test_generation_drafts_validation.py`
- [ ] T070 [P] Batch pytest `-k "tender_requirement or generation or epic6"` green in `backend/tests/`
- [ ] T071 Verify `GET /module-suggestions/{id}` fields satisfy Epic 6 consumption in `backend/tests/contract/test_module_suggestion_adoption.py`
- [ ] T072 [P] Add generation audit fields checklist comment in `backend/src/services/generation/snapshot_writer.py`（G4 验收对照 FR-010）

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 Setup → Phase 2 Foundational (BLOCKS ALL) → US1 → US2 → US3 → US4 → US5 → US6 → UI → Polish
```

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Foundational | 招标约束 + 建议采纳；Epic 5 module-suggestions 扩展 |
| US2 | Foundational | VariableResolver；Epic 2 TemplateVariable 只读 |
| US3 | US1 + US2 | 需 adopted suggestion + 变量预检；核心生成 |
| US4 | US3 | 快照/草稿 GET；生成时 snapshot 已写入 |
| US5 | US3 | 条件章节集成进生成管线 |
| US6 | US3 + US4 | 工作流建立在已有 draft/snapshot 上 |
| UI | US1–US6 API | 前端集成 |

### Parallel Opportunities

- **Phase 2**: T006–T010 五模型并行；T016 与 T014 可并行
- **US1**: T017–T018 契约测试并行
- **US2**: T023–T024 测试并行
- **US3**: T028–T030 测试并行；T032–T033 resolver/checker 并行
- **US5**: T047 单元测试与 T049 evaluator 实现可交错（先测后实现）
- **UI**: T058 + T062 两个 service 客户端并行；T064 SnapshotDetailDrawer 与 T061 VariableFillPanel 并行

### Parallel Example: User Story 3 Services

```bash
backend/src/services/generation/input_priority_resolver.py
backend/src/services/generation/compliance_checker.py
backend/tests/unit/test_input_priority_resolver.py
backend/tests/unit/test_citation_binder.py
```

### Parallel Example: Foundational Models

```bash
backend/src/models/tender_requirement_context.py
backend/src/models/generation_task.py
backend/src/models/chapter_draft.py
backend/src/models/generation_snapshot.py
backend/src/models/prompt_config_version.py
```

---

## Implementation Strategy

### MVP First（推荐停点）

1. Phase 1–2：基建（migration + models + schemas + prompt seed）  
2. Phase 3–5：US1 + US2 + **US3（章节草稿生成）**  
3. **STOP & VALIDATE**：quickstart 场景 1–4 + `test_epic6_quickstart_flow.py`  
4. 再叠加 US4–US6 + UI + Polish

### Incremental Delivery

| 切片 | Tasks | 可演示 |
|------|-------|--------|
| P0 基建 | T001–T016 | migration + prompt seed |
| P1 约束 | T017–T022 | tender-requirements + adoption |
| P1 变量 | T023–T027 | 必填拦截 |
| P1 生成 | T028–T041 | 章节草稿 + mock LLM |
| P1 审计 | T042–T046 | snapshot/draft GET |
| P2 条件 | T047–T051 | 条件章节 + 冲突优先级 |
| P2 工作流 | T052–T057 | accept/discard/regenerate |
| UI | T058–T066 | OutlineCenter 向导 |
| 收尾 | T067–T072 | quickstart 全绿 |

### Parallel Team Strategy

- Dev A：Foundational + US3 生成后端（T005–T041）  
- Dev B：US1 + US2 + US4–US6 API（T017–T027, T042–T057）  
- Dev C：OutlineCenter UI（T058–T066）  
- 汇合：integration + quickstart（T031, T048, T067, T070）

---

## Notes

- 生成输入 MUST 仅引用 `status=published` 正式资产；候选永不作输入  
- LLM 未配置时返回 `LLM_UNAVAILABLE`；CI 使用 mock `llm_client.chat_completion`  
- `generation_snapshots` append-only；accept/discard 只改 `chapter_drafts`  
- 招标约束优先于模板：`InputPriorityResolver` + `ConflictDetector` 双保险  
- Out of scope：Template Instance、完整招标解析、多章节联动、草稿 auto-publish  
- 每个 Task：Red → Green → Refactor；先跑对应 test 确认 FAIL  
- 单任务避免同文件冲突（尤其 `generation_service.py`、`generation.py`）

---

## Task Summary

| Phase | Tasks | Count |
|-------|-------|-------|
| Setup | T001–T004 | 4 |
| Foundational | T005–T016 | 12 |
| US1 | T017–T022 | 6 |
| US2 | T023–T027 | 5 |
| US3 | T028–T041 | 14 |
| US4 | T042–T046 | 5 |
| US5 | T047–T051 | 5 |
| US6 | T052–T057 | 6 |
| UI | T058–T066 | 9 |
| Polish | T067–T072 | 6 |
| **Total** | **T001–T072** | **72** |

**Suggested MVP scope**: Phase 1–2 + US1 + US2 + US3（T001–T041，共 41 tasks）  
**Full spec acceptance**: T001–T066（至 UI 集成）  
**Production-ready**: T001–T072（含 quickstart + Constitution 验收）
