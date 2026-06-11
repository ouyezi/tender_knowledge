# Implementation Plan: Epic 1 来源导入与文件分类确认

**Branch**: `002-source-import-classify` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-source-import-classify/spec.md`

## Summary

建立 V3.0 **单文件导入统一入口**：上传落盘 → File Import 记录 → 异步 hash/用途建议 →
人工确认用途与分类 → 按 `file_purpose` 创建下游任务占位。复用 Epic 0 FastAPI + PostgreSQL +
React 单体仓库；新增本地文件存储、导入任务表、来源导入中心 UI。不实现模板/标书实际解析
（Epic 2/3）。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15 (psycopg),
python-multipart（上传）, hashlib（SHA-256）; React 18, Ant Design 5, Vite

**Storage**: PostgreSQL 15（File Import、任务、审计）；本地文件系统 `STORAGE_ROOT`
（Docker volume `upload_data`）

**Testing**: pytest, httpx（上传/确认契约）；Vitest（前端表单）；集成测试覆盖上传→确认→分流

**Target Platform**: Linux/macOS 开发；Docker Compose；生产 Linux 容器

**Project Type**: web-service（backend API + admin frontend）

**Performance Goals**: 上传返回 import_id P95 < 5s（SC-002）；确认保存 P95 < 1s（SC-005）；
列表分页 P95 < 500ms（常规页大小）

**Constraints**: 单文件仅；kb 级隔离；人工确认优先于建议；无 RBAC（X-Operator-Id）；
已发布对象不可物理删除；用途确认前禁止下游解析任务

**Scale/Scope**: 单 KB 日导入 ~500 文件；单文件上限 50MB（docx/pdf/ppt）；Epic 1 不含
目录批量导入、实际解析、候选工作台

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | Epic 1 spec + plan 后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 导入是生产起点；输出为带用途/分类的治理记录 + 下游入口，非裸文件仓库 | ✅ | ✅ |
| G3 | Human Confirmation Gate | 建议与正式字段分离；确认前不路由；无静默写入 file_purpose | ✅ | ✅ (suggestion 表) |
| G4 | Chapter-First & Traceability | chapter_taxonomy_id + import_audit + trace_id + classification_reference | ✅ | ✅ |
| G5 | Retrieval Before Generation | 本 Epic 无生成；仅分类读接口消费 | ✅ | ✅ |
| G6 | MVP Scope | 单文件；无文件夹批量；无模板/标书解析实现 | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/002-source-import-classify/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── file-import-api.md
│   └── file-purpose-confirm-api.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── routes/
│   │       └── file_imports.py      # upload, list, detail, retry, confirm, ignore
│   ├── models/
│   │   ├── file_import.py
│   │   ├── file_purpose_suggestion.py
│   │   ├── import_task.py
│   │   ├── downstream_task_entry.py
│   │   └── import_audit_log.py
│   ├── schemas/
│   │   └── file_import.py
│   ├── services/
│   │   ├── file_storage.py          # STORAGE_ROOT adapter
│   │   ├── file_hash.py
│   │   ├── duplicate_detection.py
│   │   ├── purpose_suggestion.py    # rule + optional LLM
│   │   ├── file_import_service.py
│   │   ├── confirm_service.py       # confirm, ignore, route
│   │   └── import_task_runner.py    # background hash/classify
│   └── main.py                      # register router
├── tests/
│   ├── contract/test_file_import_api.py
│   ├── integration/test_upload_confirm_flow.py
│   └── unit/test_purpose_suggestion.py
└── fixtures/                        # sample files for tests

frontend/
├── src/
│   ├── pages/
│   │   └── FileImportCenter/
│   │       ├── index.tsx            # 列表 + 上传
│   │       ├── ConfirmDrawer.tsx    # 用途确认
│   │       └── TaskLogDrawer.tsx
│   ├── services/
│   │   └── fileImports.ts
│   └── App.tsx                      # /file-imports route

docker-compose.yml                   # + upload_data volume, STORAGE_ROOT env
data/uploads/                        # gitignored local storage
```

**Structure Decision**: 延续 Epic 0 monorepo（Option 2）。新增 `file_imports` 路由与
**来源导入中心** 单页；任务日志先内嵌于导入详情，任务中心全局视图可后续迭代。

## Complexity Tracking

> 无 Constitution 违规项；本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 Output

See [research.md](./research.md) — 存储、两阶段上传、建议引擎、去重版本链、分流占位、
乐观锁、文件限制均已决议。

## Phase 1 Output

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| File Import API | [contracts/file-import-api.md](./contracts/file-import-api.md) |
| File Purpose Confirm API | [contracts/file-purpose-confirm-api.md](./contracts/file-purpose-confirm-api.md) |
| Validation guide | [quickstart.md](./quickstart.md) |

## Implementation Notes (for tasks.md)

### User Story → Component mapping

| Story | Backend | Frontend |
|-------|---------|----------|
| P1 单文件上传 | `file_imports` POST, storage, hash task | FileImportCenter 上传区 + 列表 |
| P2 建议与确认 | suggestion service, confirm/ignore | ConfirmDrawer + Epic 0 分类选择器 |
| P3 分流/去重/重试 | duplicate_detection, downstream entries, retry | 重复弹窗、重试按钮、TaskLogDrawer |

### Foundational tasks (blocking)

1. Models + migrations：`file_imports`, `file_purpose_suggestions`, `import_tasks`,
   `downstream_task_entries`, `import_audit_logs`；扩展 `classification_reference.object_type`
2. `file_storage` + docker volume + env
3. Upload API + background runner（hash + classify）
4. Confirm/ignore + routing service
5. Audit + trace 复用 `AuditMiddleware`

### Out of scope (explicit)

- 模板文件解析（Epic 2）
- 实际标书 Document Tree / Bid Outline（Epic 3）
- Candidate Knowledge 工作台（Epic 4）
- 目录/批量导入
- 全局任务中心 UI（可列后续任务；本 Epic 导入详情内任务日志即可）

### Epic 依赖

| 依赖 | 用途 |
|------|------|
| Epic 0 Product Category / Chapter Taxonomy | 确认页选项、建议匹配、classification_reference |
| Epic 0 Knowledge Base | kb_id 隔离、kb_write_guard |

### Epic 下游

| 消费者 | 输入 |
|--------|------|
| Epic 2 | `downstream_task_entries` where `template_file_parse` |
| Epic 3 | `document_parse`, `bid_outline_extract`, `candidate_knowledge_generate` |

## Next Step

运行 `/speckit-tasks` 生成 `tasks.md`，再按 TDD 实现 P1 → P2 → P3。
