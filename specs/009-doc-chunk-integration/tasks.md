# Tasks: 实际标书解析接入 doc_chunk

**Input**: Design documents from `/specs/009-doc-chunk-integration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Per `.specify/memory/constitution.md`, each slice follows TDD (Write Test → Implement → Refactor).

**Organization**: Tasks grouped by user story; foundational adapters block US1–US3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1–US5 from spec.md

## Path Conventions

- Backend: `backend/src/`, `backend/tests/`
- Specs: `specs/009-doc-chunk-integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: doc_chunk 依赖、配置与包骨架

- [ ] T001 Add `doc-chunk` editable path dependency in `backend/pyproject.toml` pointing to `../../tender_skills`
- [ ] T002 [P] Add doc_chunk settings (`use_doc_chunk_parse`, retention, skip_enrich) in `backend/src/config.py`
- [ ] T003 [P] Create package scaffold `backend/src/services/doc_chunk/__init__.py` exporting public entrypoints
- [ ] T004 [P] Create `ImportContext` and `ImportResult` dataclasses in `backend/src/services/doc_chunk/types.py` per `data-model.md`
- [ ] T005 Export minimal workspace fixture tree under `backend/tests/fixtures/doc_chunk_workspace_minimal/` (manifest, outline, linkage, document_tree, chunks, images manifest)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 工作区生命周期、pipeline 封装、blocks 转换——阻塞所有用户故事

**⚠️ CRITICAL**: US1–US3 不得在此阶段完成前开始

### Tests for Foundational

- [ ] T006 [P] Unit test workspace path create/cleanup in `backend/tests/unit/test_doc_chunk_workspace_manager.py`
- [ ] T007 [P] Unit test `chunk_blocks_to_content` image_ref→asset_id in `backend/tests/unit/test_doc_chunk_blocks_v1.py`
- [ ] T008 [P] Unit test workspace JSON loader validation in `backend/tests/unit/test_doc_chunk_workspace_loader.py`

### Implementation for Foundational

- [ ] T009 Implement `backend/src/services/doc_chunk/workspace_manager.py` (create path, cleanup on success/failure, retention)
- [ ] T010 Implement `backend/src/services/doc_chunk/workspace_loader.py` (load manifest, outline, tree, linkage, chunks; validate schema_version)
- [ ] T011 Implement `backend/src/services/doc_chunk/blocks_v1.py` (`chunk_blocks_to_content` per contracts/doc-chunk-import-internal.md)
- [ ] T012 Implement `backend/src/services/doc_chunk/pipeline_runner.py` wrapping `doc_chunk.api.run_pipeline` with `on_progress` stage mapping per research.md R5

**Checkpoint**: Foundation ready — mapper 与 import 可开始

---

## Phase 3: User Story 1 - 实际标书解析结果与改造前一致 (Priority: P1) 🎯 MVP

**Goal**: doc_chunk 路径产出 Document、Document Tree、Bid Outline，目录/节点规模与 legacy 同量级

**Independent Test**: 小型 docx 触发解析 → `status=ready` → `parse_engine=doc_chunk` → outline 与 tree 节点数合理

### Tests for User Story 1

- [ ] T013 [P] [US1] Unit test `media_assets` mapper in `backend/tests/unit/test_doc_chunk_media_assets_mapper.py`
- [ ] T014 [P] [US1] Unit test `document_tree` mapper (node types, parent links, unique UUIDs) in `backend/tests/unit/test_doc_chunk_document_tree_mapper.py`
- [ ] T015 [P] [US1] Unit test `bid_outline` mapper from outline+linkage in `backend/tests/unit/test_doc_chunk_bid_outline_mapper.py`
- [ ] T016 [US1] Contract test doc_chunk parse path in `backend/tests/contract/test_actual_bid_parse_doc_chunk.py` (trigger → ready, parse_engine field)

### Implementation for User Story 1

- [ ] T017 [P] [US1] Implement `backend/src/services/doc_chunk/mappers/media_assets.py` (images/manifest → DocumentMediaAsset, image_ref_map)
- [ ] T018 [P] [US1] Implement `backend/src/services/doc_chunk/mappers/document_tree.py` (document_tree.json → DocumentTreeNode rows)
- [ ] T019 [US1] Implement `backend/src/services/doc_chunk/mappers/bid_outline.py` (outline.json + linkage → BidOutline/BidOutlineNode, extract_strategy mapping)
- [ ] T020 [US1] Implement partial `import_workspace` steps 1–4 in `backend/src/services/doc_chunk/import_service.py` (media → tree → outline)
- [ ] T021 [US1] Wire doc_chunk branch in `backend/src/services/actual_bid_parse_runner.py` (docm → pipeline → import partial; legacy branch unchanged)
- [ ] T022 [US1] Extend `llm_progress` with `parse_engine`, `doc_chunk_stages`, counts in `backend/src/services/actual_bid_parse_runner.py`

**Checkpoint**: 解析可完成并落库 Document Tree + Bid Outline；候选可尚未生成

---

## Phase 4: User Story 3 - 候选知识正文与溯源完整 (Priority: P1)

**Goal**: linkage 主 chunk → CandidateKnowledge（blocks_v1），含图片 asset_id，source_node_id 可追溯

**Independent Test**: 解析后 `pending` 候选列表条数 ≈ outline；抽样正文含 paragraph/table/image

### Tests for User Story 3

- [ ] T023 [P] [US3] Unit test candidates mapper (Preface skip, ignore type, blocks_v1) in `backend/tests/unit/test_doc_chunk_candidates_mapper.py`
- [ ] T024 [P] [US3] Unit test full `import_service` orchestration with minimal fixture in `backend/tests/unit/test_doc_chunk_import_service.py`
- [ ] T025 [US3] Integration test parse→candidates flow in `backend/tests/integration/test_doc_chunk_parse_flow.py`

### Implementation for User Story 3

- [ ] T026 [US3] Implement `backend/src/services/doc_chunk/mappers/candidates.py` (linkage primary chunk → CandidateKnowledge)
- [ ] T027 [US3] Complete `import_service.py` steps 5–7 (classify headings, import candidates, persist parse_suggestion)
- [ ] T028 [US3] Integrate enrich metadata hints → KB taxonomy/product UUID resolution in `backend/src/services/doc_chunk/mappers/candidates.py` or delegate to `chunk_classification_service.py`
- [ ] T029 [US3] Finish `actual_bid_parse_runner.py` doc_chunk path: full import + downstream checkpoint + suggestion payload

**Checkpoint**: US1 + US3 完整流水线可演示（MVP 完成）

---

## Phase 5: User Story 2 - 目录确认向导无感知切换 (Priority: P1)

**Goal**: 既有 API 与 ActualBidParseConfirmWizard 无需前端改动即可工作

**Independent Test**: quickstart 场景 2；契约测试 GET task / outline / candidates 形状不变

### Tests for User Story 2

- [ ] T030 [P] [US2] Contract test task detail optional fields per `contracts/actual-bid-parse-api-delta.md` in `backend/tests/contract/test_actual_bid_parse_doc_chunk.py`
- [ ] T031 [P] [US2] Contract test parse-suggestion `doc_chunk` payload extension in `backend/tests/contract/test_actual_bid_parse_suggestion.py`

### Implementation for User Story 2

- [ ] T032 [US2] Ensure `bid_outline_diff_service` receives doc_chunk outline entries on `force_reparse` + locked outline in `backend/src/services/actual_bid_parse_runner.py`
- [ ] T033 [US2] Verify `document_parse_suggestion` payload includes outline quality + doc_chunk manifest summary in import finalize step

**Checkpoint**: 确认向导端到端无 API 破坏性变更

---

## Phase 6: User Story 5 - 可回退与可观测 (Priority: P2)

**Goal**: `USE_DOC_CHUNK_PARSE=false` 走 legacy；任务可识别 parse_engine

**Independent Test**: quickstart 场景 3；legacy 契约全绿

### Tests for User Story 5

- [ ] T034 [P] [US5] Contract regression with `use_doc_chunk_parse=False` in `backend/tests/contract/test_actual_bid_parse_legacy.py` (or env override in existing contract tests)

### Implementation for User Story 5

- [ ] T035 [US5] Guard legacy branch in `backend/src/services/actual_bid_parse_runner.py` when `Settings.use_doc_chunk_parse` is false
- [ ] T036 [US5] Set `llm_progress.parse_engine=legacy` on legacy path for observability

**Checkpoint**: 双路径可切换、可观测

---

## Phase 7: User Story 4 - 模板标书解析路径不受影响 (Priority: P2)

**Goal**: template_parse_runner 不调用 doc_chunk

**Independent Test**: quickstart 场景 4；模板契约测试通过

### Tests for User Story 4

- [ ] T037 [US4] Regression test template parse unchanged in `backend/tests/contract/test_template_parse_runner.py` (or existing template contract suite)

### Implementation for User Story 4

- [ ] T038 [US4] Audit imports: ensure `template_parse_runner.py` has no dependency on `services.doc_chunk` (document-only if already true)

**Checkpoint**: 模板路径隔离确认

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 大文件回归、文档与清理

- [ ] T039 [P] Optional integration test with `DOC_CHUNK_CANBU_FIXTURE` in `backend/tests/integration/test_doc_chunk_canbu_parse.py` (skip if env unset)
- [ ] T040 Run full `pytest backend/tests/contract backend/tests/unit/test_doc_chunk_*` and fix failures
- [ ] T041 [P] Document env vars in `specs/009-doc-chunk-integration/quickstart.md` cross-check and `backend/README.md` if present
- [ ] T042 [P] Add `BidOutlineExtractStrategy.doc_chunk` enum value if needed in `backend/src/models/bid_outline.py` + migration if enum stored in DB

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 Setup → Phase 2 Foundational → Phase 3 US1 → Phase 4 US3
                                              ↘ Phase 5 US2 (after US3)
Phase 6 US5 ∥ Phase 7 US4 (after Phase 2; US5 needs runner branch from US1)
Phase 8 Polish (after US1–US5 desired scope)
```

### User Story Dependencies

| Story | Depends on | Notes |
|-------|------------|-------|
| US1 | Phase 2 | MVP core |
| US3 | US1 import partial | 候选依赖 tree/outline/linkage |
| US2 | US3 | 向导需要完整 ready 任务 |
| US5 | US1 runner branch | legacy 与 doc_chunk 并列 |
| US4 | Phase 1 only | 独立回归 |

### Parallel Opportunities

- T002, T003, T004 parallel after T001
- T006, T007, T008 parallel
- T013, T014, T015 parallel (tests before T017–T019)
- T017, T018 parallel before T019
- T030, T031 parallel
- T039, T041, T042 parallel in Polish

### Parallel Example: User Story 1 mappers

```bash
# After T016 fails (tests written):
# Parallel:
T017 media_assets.py
T018 document_tree.py
# Then sequential:
T019 bid_outline.py → T020 import_service partial → T021 runner
```

---

## Implementation Strategy

### MVP First (US1 + US3)

1. Complete Phase 1–2
2. Complete Phase 3 (tree + outline 落库)
3. Complete Phase 4 (candidates)
4. **STOP and VALIDATE**: quickstart 场景 1
5. Add Phase 5 US2 verification

### Incremental Delivery

1. Setup + Foundational
2. US1 → 可解析目录与文档树
3. US3 → 完整候选流水线（可演示 MVP）
4. US2 → 确认向导契约
5. US5 + US4 → 回退与模板隔离
6. Polish → 大文件与文档

---

## Notes

- 总任务数：**42**
- US1: 10 tasks (T013–T022) | US3: 7 (T023–T029) | US2: 4 (T030–T033) | US5: 3 (T034–T036) | US4: 2 (T037–T038)
- Setup+Foundational: 12 (T001–T012) | Polish: 4 (T039–T042)
- 前端无必需任务；`ActualBidParseConfirmWizard.tsx` 不在本特性修改范围
- legacy 模块保留不删除：`docx_document_walker.py`, `docx_toc_extractor.py`, `candidate_generate_service.py`
