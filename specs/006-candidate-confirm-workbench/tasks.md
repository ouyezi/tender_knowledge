# Tasks: Epic 4 候选知识确认工作台

**Input**: Design documents from `/specs/006-candidate-confirm-workbench/`  
**Brainstorming design**: `docs/superpowers/specs/2026-06-14-epic4-candidate-confirm-workbench-design.md`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md；Epic 0–3 已交付

**Tests**: 遵循 `.specify/memory/constitution.md` TDD — 每 Story 先写失败测试再实现

**Organization**: 按用户故事分组；Foundational 对应 design P0；US1–US3 对应 P1 单条闭环

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 路由壳与前端入口，不阻塞 migration

- [ ] T001 Register Epic 4 route modules (`candidates` extensions, `candidate_batch`, `candidate_audit_logs`, `knowledge_units`, `wikis`, `manual_assets`) in `backend/src/main.py`
- [ ] T002 [P] Add frontend routes `/candidates/confirm/:candidateId` and `/candidates/audit` in `frontend/src/App.tsx`
- [ ] T003 [P] Create empty page shells `frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx` and `frontend/src/pages/CandidateCenter/CandidateAuditPanel.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: P0 基建 — migration、适配器、审计模型；**阻塞所有用户故事**

**⚠️ CRITICAL**: Phase 3+ 不得开始，直到本 Phase checkpoint 通过

- [ ] T004 Create Alembic migration `backend/alembic/versions/*_epic4_candidate_confirm.py`（候选扩展字段 + `knowledge_units` + `wikis` + `manual_assets` + `candidate_confirm_audit_logs` + 正式表来源字段）
- [ ] T005 Extend `CandidateKnowledge` with confirmed/lineage/publish fields in `backend/src/models/candidate_knowledge.py`
- [ ] T006 Extend `CandidateKnowledgeStub` with matching fields in `backend/src/models/candidate_knowledge_stub.py`
- [ ] T007 [P] Create `KnowledgeUnit` model in `backend/src/models/knowledge_unit.py`
- [ ] T008 [P] Create `Wiki` model in `backend/src/models/wiki.py`
- [ ] T009 [P] Create `ManualAsset` model in `backend/src/models/manual_asset.py`
- [ ] T010 [P] Create `CandidateConfirmAuditLog` model in `backend/src/models/candidate_confirm_audit_log.py`
- [ ] T011 Register new models in `backend/src/models/__init__.py`
- [ ] T012 Extend `CandidateKnowledgeType` enum（7 类型 + ignore）in `backend/src/models/candidate_knowledge.py` and `backend/src/models/candidate_knowledge_stub.py`
- [ ] T013 Implement `CandidateAdapter` (`doc_`/`tpl_` 解析 + `CandidateView`) in `backend/src/services/candidate_adapter.py`
- [ ] T014 Implement audit write helper in `backend/src/services/candidate_audit_service.py`
- [ ] T015 [P] Unit test adapter ID parsing and terminal-state guards in `backend/tests/unit/test_candidate_adapter.py`

**Checkpoint**: migration 可执行；adapter 单测通过；inactive KB 写操作仍 403

---

## Phase 3: User Story 1 — 浏览与筛选待确认候选 (Priority: P1) 🎯 MVP 入口

**Goal**: ProTable 列表 + 扩展 API 筛选；未确认候选检索隔离负向验证

**Independent Test**: 打开 `/candidates`，按 import_id / 章节类型 / 候选类型 / 状态筛选；结果与 API 一致；pending 候选不出现在 `GET /knowledge-units`

### Tests for User Story 1

- [ ] T016 [P] [US1] Contract test list filters (`chapter_taxonomy_id`, `product_category_id`, `confidence_min`) in `backend/tests/contract/test_candidate_list_filters.py`
- [ ] T017 [P] [US1] Contract test retrieval isolation (pending candidate absent from formal KU list) in `backend/tests/contract/test_candidate_retrieval_isolation.py`

### Implementation for User Story 1

- [ ] T018 [US1] Extend `list_candidates` query filters in `backend/src/api/routes/candidates.py`
- [ ] T019 [P] [US1] Extend list params in `frontend/src/services/candidates.ts`
- [ ] T020 [US1] Upgrade `CandidateCenter` to ProTable with filter toolbar in `frontend/src/pages/CandidateCenter/index.tsx`
- [ ] T021 [P] [US1] Add row action「发布」navigate to `/candidates/confirm/:candidateId` in `frontend/src/pages/CandidateCenter/index.tsx`

**Checkpoint**: US1 可独立演示列表筛选与检索隔离

---

## Phase 4: User Story 2 — 查看与编辑候选详情 (Priority: P1)

**Goal**: PATCH 编辑 pending 候选；Drawer 轻编辑；终态不可编辑

**Independent Test**: Drawer 修改标题/摘要/分类 → 保存 → 刷新持久化；已发布候选 PATCH 返回 409

### Tests for User Story 2

- [ ] T022 [P] [US2] Contract test PATCH success and `CANDIDATE_NOT_EDITABLE` in `backend/tests/contract/test_candidate_edit.py`

### Implementation for User Story 2

- [ ] T023 [US2] Implement `candidate_edit_service.py` in `backend/src/services/candidate_edit_service.py`
- [ ] T024 [US2] Add `PATCH /candidates/{candidate_id}` in `backend/src/api/routes/candidates.py`
- [ ] T025 [US2] Extract `CandidateDetailDrawer.tsx` with edit Form + save in `frontend/src/pages/CandidateCenter/CandidateDetailDrawer.tsx`
- [ ] T026 [US2] Add `patchCandidate()` in `frontend/src/services/candidates.ts` and wire Drawer in `frontend/src/pages/CandidateCenter/index.tsx`

**Checkpoint**: US1 + US2 可独立演示浏览、筛选、轻编辑

---

## Phase 5: User Story 3 — 将候选发布为正式知识资产 (Priority: P1)

**Goal**: 7 种 `confirm_as` + ignore；幂等发布；全屏两栏 Tab 页；正式对象只读 GET

**Independent Test**: 全屏页发布 doc 候选为 KU、tpl 候选为 template_chapter、pattern 候选为 confirmed；`confirmed_object_id` 可追溯；重试不重复 INSERT

### Tests for User Story 3

- [ ] T027 [P] [US3] Unit test `candidate_publish_validator.py` rules in `backend/tests/unit/test_candidate_publish_validator.py`
- [ ] T028 [P] [US3] Contract test confirm all `confirm_as` + idempotent republish in `backend/tests/contract/test_candidate_confirm.py`
- [ ] T029 [US3] Integration test dual-channel publish + retry in `backend/tests/integration/test_candidate_publish_flow.py`

### Implementation for User Story 3

- [ ] T030 [US3] Implement `candidate_publish_validator.py` in `backend/src/services/candidate_publish_validator.py`
- [ ] T031 [P] [US3] Implement `ku_publisher.py` in `backend/src/services/publishers/ku_publisher.py`
- [ ] T032 [P] [US3] Implement `wiki_publisher.py` in `backend/src/services/publishers/wiki_publisher.py`
- [ ] T033 [P] [US3] Implement `template_chapter_publisher.py` in `backend/src/services/publishers/template_chapter_publisher.py`
- [ ] T034 [P] [US3] Implement `manual_asset_publisher.py` in `backend/src/services/publishers/manual_asset_publisher.py`
- [ ] T035 [P] [US3] Implement `chapter_pattern_publisher.py` in `backend/src/services/publishers/chapter_pattern_publisher.py`
- [ ] T036 [P] [US3] Implement `product_category_publisher.py` in `backend/src/services/publishers/product_category_publisher.py`
- [ ] T037 [P] [US3] Implement `ignore_handler.py` in `backend/src/services/publishers/ignore_handler.py`
- [ ] T038 [US3] Implement orchestrator `candidate_publish_service.py` in `backend/src/services/candidate_publish_service.py`
- [ ] T039 [US3] Add `POST /confirm` and `POST /retry-publish` in `backend/src/api/routes/candidates.py`
- [ ] T040 [P] [US3] Add read-only `knowledge_units.py` routes in `backend/src/api/routes/knowledge_units.py`
- [ ] T041 [P] [US3] Add read-only `wikis.py` routes in `backend/src/api/routes/wikis.py`
- [ ] T042 [P] [US3] Add read-only `manual_assets.py` routes in `backend/src/api/routes/manual_assets.py`
- [ ] T043 [US3] Implement two-column Tab ConfirmPage (编辑/发布 + dynamic confirm_as fields) in `frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx`
- [ ] T044 [US3] Add `confirmCandidate()` / `retryPublishCandidate()` in `frontend/src/services/candidates.ts`

**Checkpoint**: **核心 MVP** — 单条 7 类型发布闭环可演示（design P1）

---

## Phase 6: User Story 4 — 合并、拆分与忽略候选 (Priority: P2)

**Goal**: merge/split API + Modal；lineage 保留；审计记录

**Independent Test**: 合并两条 pending → source=merged；拆分一条 → N 条新 pending；审计含 merge/split action

### Tests for User Story 4

- [ ] T045 [P] [US4] Contract test merge/split error cases in `backend/tests/contract/test_candidate_merge_split.py`

### Implementation for User Story 4

- [ ] T046 [US4] Implement `candidate_merge_service.py` in `backend/src/services/candidate_merge_service.py`
- [ ] T047 [US4] Add `POST /candidates/merge` and `POST /candidates/{id}/split` in `backend/src/api/routes/candidates.py`
- [ ] T048 [US4] Implement `CandidateMergeModal.tsx` in `frontend/src/pages/CandidateCenter/CandidateMergeModal.tsx`
- [ ] T049 [US4] Implement `CandidateSplitModal.tsx` in `frontend/src/pages/CandidateCenter/CandidateSplitModal.tsx`
- [ ] T050 [US4] Wire merge/split actions in `frontend/src/pages/CandidateCenter/index.tsx`

**Checkpoint**: US4 可独立于 batch 演示

---

## Phase 7: User Story 5 — 批量确认与批量驳回 (Priority: P2)

**Goal**: batch confirm/reject；Modal 策略 + Result Drawer；部分失败不回滚

**Independent Test**: 多选 50 条 batch confirm；30s 内返回汇总；失败项可跳转全屏重试

### Tests for User Story 5

- [ ] T051 [P] [US5] Contract test batch partial failure in `backend/tests/contract/test_candidate_batch.py`

### Implementation for User Story 5

- [ ] T052 [US5] Implement batch orchestration in `backend/src/api/routes/candidate_batch.py`
- [ ] T053 [US5] Implement `BatchConfirmModal.tsx`（统一 KU / 全部忽略 / 沿用建议类型）in `frontend/src/pages/CandidateCenter/BatchConfirmModal.tsx`
- [ ] T054 [US5] Implement `BatchResultDrawer.tsx` in `frontend/src/pages/CandidateCenter/BatchResultDrawer.tsx`
- [ ] T055 [US5] Add batch API client in `frontend/src/services/candidates.ts` and wire ProTable rowSelection in `frontend/src/pages/CandidateCenter/index.tsx`

**Checkpoint**: US5 批量路径可端到端验收（SC-006）

---

## Phase 8: User Story 6 — 查看确认操作日志 (Priority: P3)

**Goal**: audit list API + UI Tab；按 candidate/batch/action 筛选

**Independent Test**: 发布/批量后 audit Tab 可见 publish、batch_confirm、publish_failed 记录

### Tests for User Story 6

- [ ] T056 [P] [US6] Contract test audit log filters in `backend/tests/contract/test_candidate_audit_logs.py`

### Implementation for User Story 6

- [ ] T057 [US6] Implement `GET /candidate-audit-logs` in `backend/src/api/routes/candidate_audit_logs.py`
- [ ] T058 [US6] Add `frontend/src/services/candidateAudit.ts`
- [ ] T059 [US6] Implement audit list UI in `frontend/src/pages/CandidateCenter/CandidateAuditPanel.tsx` and wire Tab/route in `frontend/src/pages/CandidateCenter/index.tsx`

**Checkpoint**: spec 全部 6 个用户故事可独立验收

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: quickstart 全场景、性能、文档（design P4）

- [ ] T060 Run quickstart scenarios 1–9 from `specs/006-candidate-confirm-workbench/quickstart.md` and fix gaps
- [ ] T061 [P] Vitest smoke for ConfirmPage confirm_as field switching in `frontend/src/pages/CandidateCenter/CandidateConfirmPage.test.tsx`
- [ ] T062 [P] Batch pytest `-k "candidate_confirm or candidate_publish or candidate_batch"` green in `backend/tests/`
- [ ] T063 Mark design doc Status Approved in `docs/superpowers/specs/2026-06-14-epic4-candidate-confirm-workbench-design.md`

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 Setup → Phase 2 Foundational (BLOCKS ALL) → US1 → US2 → US3 → US4 → US5 → US6 → Polish
```

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Foundational | 可先用现有只读 API 增强 |
| US2 | US1（UI 壳） | PATCH 独立于 publish |
| US3 | US2 推荐 | 发布使用编辑后的字段 |
| US4 | US3 | merge/split 后仍走 confirm |
| US5 | US3 | batch 复用 publish_service |
| US6 | US3+（有 audit 写入） | 最佳在 batch 后验收完整 action 集 |

### Parallel Opportunities

- **Phase 2**: T007–T010 四模型并行；T015 与 T013 可并行
- **US3**: T031–T037 七个 publisher 并行；T040–T042 三个只读路由并行
- **US4–US6**: 后端 contract test 与前端 Modal 可分工并行

### Parallel Example: User Story 3 Publishers

```bash
# 七 publisher 可并行（不同文件）：
backend/src/services/publishers/ku_publisher.py
backend/src/services/publishers/wiki_publisher.py
backend/src/services/publishers/template_chapter_publisher.py
# ... manual_asset, chapter_pattern, product_category, ignore_handler
```

---

## Implementation Strategy

### MVP First（推荐停点）

1. Phase 1–2：基建  
2. Phase 3–5：US1 + US2 + **US3（7 类型发布）**  
3. **STOP & VALIDATE**：quickstart 场景 2–3 + 单类型 publish 演示  
4. 再叠加 US4–US6

### Incremental Delivery（对齐 brainstorming P0–P4）

| 切片 | Tasks | 可演示 |
|------|-------|--------|
| P0 | T001–T015 | migration + adapter |
| P1 | T016–T044 | 单条全类型发布 + 全屏页 |
| P2 | T045–T055 | merge/split/batch |
| P3 | T056–T059 | 审计 Tab |
| P4 | T060–T063 | quickstart 全绿 |

### Parallel Team Strategy

- Dev A：Foundational + publish backend（T004–T042）  
- Dev B：CandidateCenter 列表/Drawer（T018–T026）  
- Dev C：ConfirmPage + batch UI（T043–T055）  
- 汇合：integration + quickstart（T029, T060）

---

## Notes

- 复合 ID `doc_` / `tpl_` 全链路保持一致  
- 每个 Task：Red → Green → Refactor；先跑对应 test 确认 FAIL  
- 单任务避免同文件冲突（尤其 `candidates.py`、`index.tsx`）  
- Out of scope：检索（Epic 5）、生成（Epic 6）、stub 表迁移

---

## Task Summary

| Phase | Tasks | Count |
|-------|-------|-------|
| Setup | T001–T003 | 3 |
| Foundational | T004–T015 | 12 |
| US1 | T016–T021 | 6 |
| US2 | T022–T026 | 5 |
| US3 | T027–T044 | 18 |
| US4 | T045–T050 | 6 |
| US5 | T051–T055 | 5 |
| US6 | T056–T059 | 4 |
| Polish | T060–T063 | 4 |
| **Total** | **T001–T063** | **63** |

**Suggested MVP scope**: Phase 1–2 + US1–US3（T001–T044，共 44 tasks）  
**Full spec acceptance**: T001–T059（至 US6）  
**Production-ready**: T001–T063（含 quickstart + Vitest）
