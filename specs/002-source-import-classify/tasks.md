# Tasks: Epic 1 来源导入与文件分类确认

**Input**: `specs/002-source-import-classify/` + `docs/superpowers/specs/2026-06-11-epic1-source-import-classify-design.md`

**Prerequisites**: Epic 0 已交付；Superpowers 详细步骤见 `docs/superpowers/plans/2026-06-11-epic1-source-import-classify.md`

**Tests**: Constitution TDD — 每切片先写失败测试再实现。

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

**Purpose**: 依赖与存储配置

- [ ] T001 Add `python-multipart` to `backend/pyproject.toml` and reinstall `.venv`
- [ ] T002 [P] Create `backend/src/config.py` with STORAGE_ROOT, LLM_API_KEY, file size limits
- [ ] T003 [P] Add `upload_data` volume to `docker-compose.yml`; document STORAGE_ROOT in `specs/002-source-import-classify/quickstart.md`

---

## Phase 2: Foundational (P0 — Blocking)

**Purpose**: 表、存储、路由壳、UI 壳 — 所有用户故事前置

**⚠️ CRITICAL**: US1–US3 不得早于本阶段完成

- [ ] T004 Create `backend/src/services/file_storage.py` + `backend/tests/unit/test_file_storage.py` (TDD)
- [ ] T005 [P] Create ORM models in `backend/src/models/file_import.py`, `file_purpose_suggestion.py`, `import_task.py`, `downstream_task_entry.py`, `import_audit_log.py`
- [ ] T006 Extend `classification_reference` object_type with `file_import` in `backend/src/models/classification_reference.py`
- [ ] T007 Update `backend/src/db/init_db.py` and `backend/src/models/__init__.py` imports
- [ ] T008 [P] Create `backend/tests/integration/test_file_import_model.py` (TDD)
- [ ] T009 Create `backend/src/api/routes/file_imports.py` with empty `GET /` list; register in `backend/src/main.py`
- [ ] T010 [P] Create `backend/tests/contract/test_file_import_list_empty.py` (TDD)
- [ ] T011 Create `frontend/src/pages/FileImportCenter/index.tsx` empty table shell
- [ ] T012 [P] Add `/file-imports` route in `frontend/src/App.tsx` and nav in `frontend/src/layout/AppShell.tsx`
- [ ] T013 Create `frontend/src/services/fileImports.ts` list API stub

**Checkpoint**: 空列表 API + 空 UI；inactive KB 写操作 403

---

## Phase 3: User Story 1 — 单文件上传与导入记录 (P1) 🎯 MVP

**Goal**: 上传文件、快速返回 import_id、异步 hash+规则建议、列表展示

**Independent Test**: quickstart 场景 1 — 上传 docx 得 import_id，列表可查，最终 need_confirm

### Tests for US1

- [ ] T014 [P] [US1] Create `backend/tests/fixtures/sample-template.docx`
- [ ] T015 [P] [US1] Create `backend/tests/contract/test_file_import_upload.py` (TDD)
- [ ] T016 [P] [US1] Create `backend/tests/unit/test_purpose_suggestion.py` for filename rules (TDD)

### Implementation for US1

- [ ] T017 [US1] Implement `backend/src/services/file_hash.py`
- [ ] T018 [US1] Implement `backend/src/services/purpose_suggestion.py` (rule engine)
- [ ] T019 [US1] Implement `backend/src/services/import_task_runner.py` (BackgroundTasks)
- [ ] T020 [US1] Implement `backend/src/services/file_import_service.py` upload orchestration
- [ ] T021 [US1] Implement `POST /file-imports` multipart in `backend/src/api/routes/file_imports.py`
- [ ] T022 [US1] Implement `GET /file-imports` list and `GET /file-imports/{id}` detail in `backend/src/api/routes/file_imports.py`
- [ ] T023 [P] [US1] Extend `backend/tests/conftest.py` with `seeded_kb` fixture
- [ ] T024 [US1] Implement upload Dragger + table in `frontend/src/pages/FileImportCenter/index.tsx`
- [ ] T025 [US1] Implement API methods in `frontend/src/services/fileImports.ts`

**Checkpoint**: SC-001/SC-002/SC-003 可本地验证

---

## Phase 4: User Story 2 — 用途建议与人工确认 (P2)

**Goal**: confirm/ignore API、乐观锁、分类引用、确认抽屉

**Independent Test**: quickstart 场景 2 — 确认保存；忽略不创建 downstream

### Tests for US2

- [ ] T026 [P] [US2] Create `backend/tests/contract/test_file_import_confirm.py` (TDD)

### Implementation for US2

- [ ] T027 [US2] Implement `backend/src/services/confirm_service.py` (confirm, ignore, classification_reference)
- [ ] T028 [US2] Add `POST .../confirm` and `POST .../ignore` in `backend/src/api/routes/file_imports.py`
- [ ] T029 [US2] Create `frontend/src/pages/FileImportCenter/ConfirmDrawer.tsx`
- [ ] T030 [US2] Wire drawer open from table; Epic 0 category TreeSelect in ConfirmDrawer
- [ ] T031 [US2] Handle 409 CONFLICT and inactive KB read-only in ConfirmDrawer

**Checkpoint**: SC-005；FR-007 未确认无下游

---

## Phase 5: User Story 3 — 分流、去重与失败重试 (P3)

**Goal**: downstream 占位、去重弹窗、重试、任务日志、可选 LLM

**Independent Test**: quickstart 场景 3–5

### Tests for US3

- [ ] T032 [P] [US3] Create `backend/tests/integration/test_downstream_routing.py` (TDD)
- [ ] T033 [P] [US3] Add duplicate upload cases to `backend/tests/contract/test_file_import_upload.py`

### Implementation for US3

- [ ] T034 [US3] Extend `confirm_service.py` with `create_downstream_entries` per file_purpose map
- [ ] T035 [US3] Implement `backend/src/services/duplicate_detection.py`
- [ ] T036 [US3] Add duplicate_action handling to upload in `file_import_service.py`
- [ ] T037 [US3] Add `GET .../downstream-entries`, `GET .../tasks`, `POST .../retry` in `file_imports.py`
- [ ] T038 [US3] Add optional LLM branch to `purpose_suggestion.py` (degrade on missing key/failure)
- [ ] T039 [US3] Create `frontend/src/pages/FileImportCenter/DuplicateFileModal.tsx`
- [ ] T040 [US3] Create `frontend/src/pages/FileImportCenter/TaskLogDrawer.tsx`
- [ ] T041 [US3] Wire retry button and duplicate modal in FileImportCenter

**Checkpoint**: SC-006–SC-009；Epic 2/3 可查 pending downstream

---

## Phase 6: Polish

- [ ] T042 [P] Update `specs/002-source-import-classify/quickstart.md` with verified commands
- [ ] T043 Run full `backend` pytest and `frontend` build; fix regressions
- [ ] T044 [P] Add `.gitignore` entry for `data/uploads/` if missing

---

## Dependencies

```text
Phase 1–2 (P0) → US1 (P1) → US2 (P2) → US3 (P3) → Polish
```

## Parallel Opportunities

- T002/T003 setup parallel
- T005/T008/T010/T012 within P0 after T004
- T014/T015/T016 test files parallel before US1 implementation
- T032/T033 parallel before US3 implementation

## MVP Scope

**US1 only** (Phase 1–3): 上传 + 列表 + 规则建议 — 可演示「文件进平台」。

**Recommended first release**: P0 + US1 + US2（完整确认门）.

## Implementation Strategy

执行 Superpowers 计划：`docs/superpowers/plans/2026-06-11-epic1-source-import-classify.md`（含逐步代码与命令）。
