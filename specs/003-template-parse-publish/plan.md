# Implementation Plan: Epic 2 模板库解析与发布

**Branch**: `003-template-parse-publish` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-template-parse-publish/spec.md`

## Summary

在 Epic 1 已确认 `file_purpose=template_file` 并写入 `downstream_task_entries`
（`template_file_parse`）的基础上，实现 **模板文件 → 结构化 Template 资产 → 人工确认 →
编辑治理 → 发布** 全链路。复用 FastAPI + PostgreSQL + React 单体架构；新增 docx 标题
结构解析、Template Library/Template/Chapter/Material/Variable/Rule 数据模型、模板解析
异步任务、解析确认与模板库中心 UI。产出 Candidate Knowledge 候选供 Epic 4 消费；已发布
Template Library 供 Epic 5/6 检索与模块建议。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15 (psycopg),
python-docx（docx 标题/段落/表格解析）, lxml（docx XML 辅助）; React 18, Ant Design 5,
Vite, @ant-design/pro-components（树表/抽屉）

**Storage**: PostgreSQL 15（Template 域实体、解析任务、审计、Candidate 占位）；
Epic 1 本地 `STORAGE_ROOT` 只读消费源文件

**Testing**: pytest + httpx（契约/集成）；Vitest（章节树 UI）；fixtures 使用
`tests/fixtures/sample-template.docx`

**Target Platform**: Linux/macOS 开发；Docker Compose；生产 Linux 容器

**Project Type**: web-service（backend API + admin frontend）

**Performance Goals**: 解析任务入队响应 P95 < 1s；50 页以内 docx 解析完成 P95 < 60s（SC-001）；
章节树加载/保存 P95 < 1s；Template Library 列表 P95 < 500ms

**Constraints**: 单文件导入；人工确认优先于机器解析；已确认结构不可被重解析静默覆盖；
未发布/未确认资产不可对外检索；MVP 变量仅 `{{key}}` 文本替换；规则仅 required/optional/
product_match；无 Bid Outline 转 Template、无 Template Instance

**Scale/Scope**: 单 KB 活跃 Template Library ~50、单 Template 章节节点 ~200、Material ~500；
Epic 2 不含 Candidate 工作台完整 UI（Epic 4）、不含模块推荐实现（Epic 5）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | Epic 2 spec + plan 后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 输出 Template/Chapter/Material 等治理资产 + Candidate，非裸 docx | ✅ | ✅ |
| G3 | Human Confirmation Gate | 解析 → 待确认 → 确认后 draft/published；重解析仅 diff | ✅ | ✅ (parse_confirm + structure_locked) |
| G4 | Chapter-First & Traceability | Template Chapter 树 + parse/confirm/publish audit + trace_id | ✅ | ✅ |
| G5 | Retrieval Before Generation | 定义已发布 Template 只读查询供 Epic 5；本 Epic 无生成 | ✅ | ✅ |
| G6 | MVP Scope | 单文件；无文件夹建库；无复杂变量/Instance/BidOutline 转 Template | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/003-template-parse-publish/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── template-parse-api.md
│   ├── template-library-api.md
│   ├── template-chapter-api.md
│   └── template-asset-api.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/routes/
│   │   ├── template_libraries.py    # library CRUD, publish, deprecate
│   │   ├── templates.py             # template query, assign library, publish
│   │   ├── template_chapters.py     # tree GET/PATCH, reorder, move
│   │   ├── template_parse.py        # trigger parse, task status, confirm parse
│   │   └── template_assets.py       # materials, variables, rules
│   ├── models/
│   │   ├── template_library.py
│   │   ├── template.py
│   │   ├── template_chapter.py
│   │   ├── template_material.py
│   │   ├── template_variable.py
│   │   ├── template_rule.py
│   │   ├── template_parse_task.py
│   │   ├── template_parse_suggestion.py   # 机器解析建议（确认前）
│   │   ├── template_structure_diff.py     # 重解析待确认差异
│   │   ├── candidate_knowledge_stub.py    # Epic 4 消费占位
│   │   └── template_audit_log.py
│   ├── services/
│   │   ├── template_parse_runner.py       # 消费 downstream + docx parse
│   │   ├── docx_outline_parser.py         # 标题树 + 编号排序
│   │   ├── docx_content_extractor.py        # 段落/表格/图片 → material
│   │   ├── template_confirm_service.py      # 解析确认 + diff 策略
│   │   ├── template_publish_service.py      # 发布校验 + 版本快照
│   │   └── variable_detector.py             # {{key}} 扫描
│   └── main.py
├── tests/
│   ├── contract/test_template_parse*.py
│   ├── integration/test_template_parse_flow.py
│   └── unit/test_docx_outline_parser.py
└── tests/fixtures/sample-template.docx

frontend/
├── src/
│   ├── pages/
│   │   └── TemplateLibraryCenter/
│   │       ├── index.tsx                  # 库列表 + Template 列表
│   │       ├── ParseConfirmDrawer.tsx     # 解析结果人工确认
│   │       ├── ChapterTreeEditor.tsx      # 章节树编辑
│   │       ├── MaterialPanel.tsx
│   │       ├── VariableRulePanel.tsx
│   │       └── PublishModal.tsx
│   ├── services/
│   │   └── templates.ts
│   └── App.tsx                            # /template-libraries route
```

**Structure Decision**: 延续 Epic 0/1 monorepo。模板域独立路由模块；解析 worker 与 Epic 1
`import_task_runner` 同进程 BackgroundTasks MVP，通过轮询 `downstream_task_entries` +
`template_parse_tasks` 驱动。模板库中心为单入口多 Tab/Drawer 页面。

## Complexity Tracking

> 无 Constitution 违规项；本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 Output

See [research.md](./research.md) — docx 解析策略、任务编排、确认/diff、发布版本、
Candidate 占位、变量/规则 MVP 均已决议。

## Phase 1 Output

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Template Parse API | [contracts/template-parse-api.md](./contracts/template-parse-api.md) |
| Template Library API | [contracts/template-library-api.md](./contracts/template-library-api.md) |
| Template Chapter API | [contracts/template-chapter-api.md](./contracts/template-chapter-api.md) |
| Template Asset API | [contracts/template-asset-api.md](./contracts/template-asset-api.md) |
| Validation guide | [quickstart.md](./quickstart.md) |

## Implementation Notes (for tasks.md)

### User Story → Component mapping

| Story | Backend | Frontend |
|-------|---------|----------|
| P1 模板解析 | `template_parse_runner`, `docx_*`, downstream 消费 | ParseConfirmDrawer 入口、任务状态 |
| P2 解析确认 | `template_confirm_service`, suggestions/diff | ParseConfirmDrawer |
| P3 章节/素材编辑 | `template_chapters`, `template_assets` | ChapterTreeEditor, MaterialPanel |
| P4 库管理与发布 | `template_libraries`, `template_publish_service` | index + PublishModal + VariableRulePanel |

### Foundational tasks (blocking)

1. Models + migrations：template 域全表 + `classification_reference.object_type` 扩展
2. `docx_outline_parser` + unit tests（sample-template.docx）
3. `template_parse_runner`：claim downstream → parse → suggestions + draft entities
4. Parse confirm API + structure lock + diff on re-parse
5. Chapter tree CRUD + audit
6. Library/Template publish + version snapshot
7. TemplateLibraryCenter UI 主流程

### Out of scope (explicit)

- Bid Outline → Template（后续 Epic/增强）
- Template Instance / Generation Snapshot 写入（Epic 6）
- Candidate Knowledge 完整工作台（Epic 4）
- 模块推荐/检索实现（Epic 5）
- conditional/mutex/asset_required 规则
- 复杂变量表达式
- 文件夹批量建 Template Library

### Epic 依赖

| 依赖 | 用途 |
|------|------|
| Epic 0 Product Category / Chapter Taxonomy | 章节类型、产品分类、建议匹配 |
| Epic 1 File Import + downstream `template_file_parse` | 解析入口、storage_path、import 审计 |

### Epic 下游

| 消费者 | 输入 |
|--------|------|
| Epic 4 | `candidate_knowledge_stubs`（status=pending_confirm） |
| Epic 5 | 已发布 `template_libraries` / `template_chapters` / `template_materials` |
| Epic 6 | 已发布 variables + rules + chapter 结构 |

## Next Step

运行 `/speckit-tasks` 生成 `tasks.md`，再按 TDD 实现 P1 → P2 → P3 → P4。
