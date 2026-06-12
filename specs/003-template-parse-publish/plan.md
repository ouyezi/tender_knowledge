# Implementation Plan: Epic 2 模板库解析与发布

**Branch**: `003-template-parse-publish` | **Date**: 2026-06-12（澄清修订） | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-template-parse-publish/spec.md`

## Summary

在 Epic 1 已确认 `file_purpose=template_file` 并写入 `downstream_task_entries`
（`template_file_parse`）的基础上，实现 **模板文件 → 结构化 Template 资产 → 人工确认 →
编辑治理 → 发布** 全链路。复用 FastAPI + PostgreSQL + React 单体架构；新增 docx 标题
结构解析、Template Library/Template/Chapter/Material/Variable/Rule 数据模型、模板解析
异步任务、解析确认与模板库中心 UI。产出 Candidate Knowledge 候选供 Epic 4 消费；已发布
Template Library 供 Epic 5/6 检索与模块建议。

**澄清修订（2026-06-12）** 在原有设计之上追加三项约束，影响解析流水线与后续实现任务：

1. **分类粒度**：细粒度分类（产品分类、章节类型、知识类型）落在 **知识块**（Template Chapter /
   Template Material / Candidate Knowledge Stub），不对导入文件做细分类；文件可能是完整标书、
   模板、产品方案或资质合集，文件级仅保留 Epic 1 的 `file_purpose`。
2. **LLM 配置**：通过环境变量（`LLM_PROVIDER` / `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`）
   切换千问或其他 OpenAI 兼容提供商；无 Key 或调用失败时降级规则引擎，不阻断解析。
3. **大文件策略**：先 docx 结构化切分，再 **按知识块分批** 调用 LLM；禁止整文件一次性 LLM。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15 (psycopg),
python-docx（docx 标题/段落/表格解析）, lxml（docx XML 辅助）; React 18, Ant Design 5,
Vite, @ant-design/pro-components（树表/抽屉）

**LLM Integration**: `src/config.py` 环境变量预设（默认千问 `qwen-plus`）；
`src/services/llm_client.py` OpenAI 兼容 HTTP 客户端；`chunk_classification_service.py`
按块调用 + 规则降级（FR-021/FR-023）

**Storage**: PostgreSQL 15（Template 域实体、解析任务、审计、Candidate 占位）；
Epic 1 本地 `STORAGE_ROOT` 只读消费源文件

**Testing**: pytest + httpx（契约/集成）；Vitest（章节树 UI）；fixtures 使用
`tests/fixtures/sample-template.docx`；LLM 路径 mock / `LLM_API_KEY=force_fail` 降级用例

**Target Platform**: Linux/macOS 开发；Docker Compose；生产 Linux 容器

**Project Type**: web-service（backend API + admin frontend）

**Performance Goals**: 解析任务入队响应 P95 < 1s；50 页以内 docx 解析完成 P95 < 60s（SC-001）；
章节树加载/保存 P95 < 1s；Template Library 列表 P95 < 500ms；**大文件（>50MB 或 >200 页）**
首批可确认知识块 P95 < 120s（SC-008，分批 LLM，非整文件）

**Constraints**: 单文件导入；人工确认优先于机器解析；已确认结构不可被重解析静默覆盖；
未发布/未确认资产不可对外检索；MVP 变量仅 `{{key}}` 文本替换；规则仅 required/optional/
product_match；无 Bid Outline 转 Template、无 Template Instance；**LLM 仅按知识块批次调用**；
文件级不做细粒度分类

**Scale/Scope**: 单 KB 活跃 Template Library ~50、单 Template 章节节点 ~200、Material ~500；
单 docx 知识块 ~500（章节+段落+素材）；Epic 2 不含 Candidate 工作台完整 UI（Epic 4）、
不含模块推荐实现（Epic 5）

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
│   │   ├── template_parse_runner.py       # 消费 downstream + docx parse + 块级 LLM 调度
│   │   ├── docx_outline_parser.py         # 标题树 + 编号排序（无 LLM）
│   │   ├── docx_content_extractor.py      # 段落/表格/图片 → material 知识块
│   │   ├── chunk_classification_service.py # 知识块级分类建议（规则 + 可选 LLM）
│   │   ├── llm_client.py                  # OpenAI 兼容客户端 + truncate_for_llm
│   │   ├── template_confirm_service.py    # 解析确认 + diff 策略
│   │   ├── template_publish_service.py    # 发布校验 + 版本快照
│   │   └── variable_detector.py           # {{key}} 扫描
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
Candidate 占位、变量/规则 MVP、**知识块级分类（R13–R15）**、**LLM 环境配置（R13）**、
**大文件分批 LLM（R15）** 均已决议。

## Clarification Delta（2026-06-12 → 后续实现变更）

| 领域 | 原设计 | 澄清后变更 | 影响组件 |
|------|--------|------------|----------|
| 分类粒度 | 文件名/标题 → 全局建议 | 每个知识块独立分类建议；文件级仅 `file_purpose` | `chunk_classification_service`, suggestion JSON, 确认 UI |
| LLM 调用 | research 倾向纯规则；LLM 未定型 | 环境变量驱动千问；`llm_client` 已落地；失败降级 | `config.py`, `llm_client.py`, `purpose_suggestion` 同模式 |
| 大文件 | 50 页 P95 < 60s | 禁止整文件 LLM；结构解析后按块批处理；进度可观测 | `template_parse_runner`, `llm_progress` 字段, quickstart 场景 7 |

### 增量任务（相对已执行基础逻辑）

1. **`chunk_classification_service`**：输入 `KnowledgeChunk`（chapter/material/candidate），
   输出 per-block `product_category_ids`、`chapter_taxonomy_id`、`knowledge_type`、
   `confidence`、`suggestion_source`（rule/llm/hybrid）。
2. **`template_parse_runner` 流水线拆分**：
   `docx 结构解析（同步，无 LLM）` → `构建知识块列表` → `分批 LLM 分类（可选）`
   → `写入 template_parse_suggestions` → `parse_ready`。
3. **Suggestion / Confirm API**：章节树、materials、candidates 每项携带块级分类字段；
   确认 UI 以知识块为粒度展示/修正（非文件级）。
4. **`template_parse_tasks.llm_progress`**：记录 `total_chunks`、`completed_chunks`、
   `failed_chunks`、`degraded_to_rule`；任务详情 API 暴露进度。
5. **测试**：无 Key 全规则路径；mock LLM 块级分类；大 fixture 验证无整文件 LLM 调用；
   `LLM_API_KEY=force_fail` 降级不断解析。

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
3. `docx_content_extractor` → 知识块列表（chapter / material / candidate 候选）
4. `chunk_classification_service` + `llm_client` 集成（块级分类 + 降级）
5. `template_parse_runner`：claim downstream → 结构解析 → 分批块级 LLM → suggestions
6. Parse confirm API + structure lock + diff on re-parse（块级分类字段）
7. Chapter tree CRUD + audit
8. Library/Template publish + version snapshot
9. TemplateLibraryCenter UI 主流程（确认抽屉按知识块展示分类）

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
