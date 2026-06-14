# Implementation Plan: Epic 3 实际标书导入与候选知识

**Branch**: `004-actual-bid-candidates` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-actual-bid-candidates/spec.md`

## Summary

在 Epic 1 已确认 `file_purpose=actual_bid` 并写入三条 `downstream_task_entries` 的基础上，
实现 **实际标书 → Document/Document Tree → Bid Outline → Candidate Knowledge（pending）**
解析链路前半段。复用 FastAPI + PostgreSQL + React 单体架构与 Epic 2 的 docx/LLM 基础设施；
新增 Document 域、Bid Outline 双轨模型、`candidate_knowledges` 表、目录中心与候选只读列表 UI。
Chapter Pattern 挖掘为独立批任务。确认/发布/检索归属 Epic 4/5。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15 (psycopg),
python-docx, lxml（docx TOC + XML）; React 18, Ant Design 5, Vite, @ant-design/pro-components

**Reuse from Epic 2**: `docx_outline_parser.py`, `llm_client.py`, `chunk_classification_service.py`
（块级分类 + 规则降级）, BackgroundTasks / downstream claim 模式

**Storage**: PostgreSQL 15（Document/Bid Outline/Candidate/Pattern 域）；Epic 1 `STORAGE_ROOT`
只读消费源文件

**Testing**: pytest + httpx（契约/集成）；Vitest（目录树 UI）；fixtures
`tests/fixtures/sample-actual-bid.docx`；LLM mock / 无 Key 降级用例

**Target Platform**: Linux/macOS 开发；Docker Compose；生产 Linux 容器

**Project Type**: web-service（backend API + admin frontend）

**Performance Goals**: 解析入队 P95 < 1s；50 页以内 docx 全流水线 P95 < 120s（SC-001 含目录编辑）；
Bid Outline 树加载/保存 P95 < 1s；候选列表 P95 < 500ms；大文件（>200 页）首批可确认块
P95 < 180s（分批 LLM，非整文件）

**Constraints**: 单文件导入；人工确认门（候选仅 pending）；Bid Outline 与 Document Tree
编辑隔离；重解析仅 diff；未确认候选不可检索；MVP 无候选确认 UI、无目录级检索、无评分点解析；
LLM 仅按章节/块批次调用

**Scale/Scope**: 单 KB 活跃 actual_bid Document ~100；单 Document 树节点 ~500；单 Bid Outline
节点 ~200；候选 ~300/文档；Epic 3 不含 Candidate 工作台（Epic 4）、检索（Epic 5）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | Epic 3 spec + plan 后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 输出 Document Tree/Bid Outline/Candidate，非裸文件存储 | ✅ | ✅ |
| G3 | Human Confirmation Gate | 候选 status=pending；outline diff 人工 apply；无静默发布 | ✅ | ✅ |
| G4 | Chapter-First & Traceability | 双轨章节 + source_node_id + audit/trace_id | ✅ | ✅ |
| G5 | Retrieval Before Generation | 候选隔离；定义 Epic 5 只读 confirmed outline 消费点 | ✅ | ✅ |
| G6 | MVP Scope | 单文件；无文件夹导入；无评分点/废标项/候选确认 | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/004-actual-bid-candidates/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── actual-bid-parse-api.md
│   ├── bid-outline-api.md
│   └── bid-candidate-api.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/routes/
│   │   ├── actual_bid_parse.py       # trigger, tasks, document, tree
│   │   ├── bid_outlines.py           # outline CRUD, diff apply
│   │   ├── candidates.py             # read-only list + detail (aggregate)
│   │   └── chapter_patterns.py       # mine trigger, pattern list
│   ├── models/
│   │   ├── document.py
│   │   ├── document_tree_node.py
│   │   ├── bid_outline.py
│   │   ├── bid_outline_node.py
│   │   ├── actual_bid_parse_task.py
│   │   ├── document_parse_suggestion.py
│   │   ├── bid_outline_structure_diff.py
│   │   ├── candidate_knowledge.py
│   │   ├── chapter_pattern.py
│   │   ├── chapter_pattern_mining_task.py
│   │   └── actual_bid_audit_log.py
│   ├── services/
│   │   ├── actual_bid_parse_runner.py    # downstream 三阶段流水线
│   │   ├── docx_document_walker.py       # 全文树 + 内容块
│   │   ├── docx_toc_extractor.py         # 内置目录优先
│   │   ├── bid_outline_extract_service.py
│   │   ├── bid_outline_diff_service.py
│   │   ├── chapter_candidate_rules.py    # 章节类型 → 候选类型
│   │   ├── candidate_generate_service.py
│   │   └── chapter_pattern_miner.py
│   └── main.py
├── tests/
│   ├── contract/test_actual_bid_parse*.py
│   ├── contract/test_bid_outline*.py
│   ├── integration/test_actual_bid_flow.py
│   └── unit/test_docx_toc_extractor.py
└── tests/fixtures/sample-actual-bid.docx

frontend/
├── src/
│   ├── pages/
│   │   ├── OutlineCenter/
│   │   │   ├── index.tsx                 # Bid Outline 列表
│   │   │   ├── OutlineTreeEditor.tsx     # 节点编辑/合并/分类
│   │   │   ├── OutlineDiffDrawer.tsx     # 重解析 diff
│   │   │   └── ParseTaskLogPanel.tsx
│   │   └── CandidateCenter/
│   │       └── index.tsx                 # 只读 pending 列表
│   ├── services/
│   │   ├── actualBidParse.ts
│   │   ├── bidOutlines.ts
│   │   └── candidates.ts
│   └── App.tsx                           # /outlines, /candidates routes
```

**Structure Decision**: 延续 Epic 0/1/2 monorepo。Document 域与 Template 域平行；`actual_bid_parse_runner`
与 `template_parse_runner` 分离但共享 docx/LLM 工具。目录中心与模板库中心 UI 模式一致。

## Complexity Tracking

> 无 Constitution 违规项；本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 Output

See [research.md](./research.md) — Document Tree walker、TOC 优先抽取、双轨编辑隔离、
`candidate_knowledges` 新表、downstream 三阶段编排、章节→候选规则、LLM 复用、
Chapter Pattern 规则挖掘、UI 范围均已决议。

## Phase 1 Output

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Actual Bid Parse API | [contracts/actual-bid-parse-api.md](./contracts/actual-bid-parse-api.md) |
| Bid Outline API | [contracts/bid-outline-api.md](./contracts/bid-outline-api.md) |
| Candidate & Pattern API | [contracts/bid-candidate-api.md](./contracts/bid-candidate-api.md) |
| Validation guide | [quickstart.md](./quickstart.md) |

## Implementation Notes (for tasks.md)

### User Story → Component mapping

| Story | Backend | Frontend |
|-------|---------|----------|
| P1 文档解析 | `actual_bid_parse_runner`, `docx_document_walker` | ParseTaskLogPanel, Document 详情 |
| P1 目录抽取 | `docx_toc_extractor`, `bid_outline_extract_service` | OutlineTreeEditor |
| P2 分类映射 | `chunk_classification_service`, tree/outline PATCH | OutlineTreeEditor 分类列 |
| P2 候选生成 | `candidate_generate_service`, `chapter_candidate_rules` | CandidateCenter 只读 |
| P3 模式挖掘 | `chapter_pattern_miner` | OutlineCenter 挖掘入口 |
| P3 目录/任务中心 | audit + task APIs | OutlineCenter + CandidateCenter |

### Foundational tasks (blocking)

1. Models + migrations：Document 域全表 + indexes
2. `docx_document_walker` + `docx_toc_extractor` + unit tests
3. `actual_bid_parse_runner`：claim downstream 三阶段 → ready
4. Document/Tree GET + metadata PATCH APIs
5. Bid Outline extract + node CRUD + batch ops + audit
6. `bid_outline_diff_service` + apply/reject APIs
7. `candidate_generate_service` + `candidate_knowledges` 写入
8. Candidates 聚合列表 API（document + template stub）
9. `chapter_pattern_miner` + mining task API
10. OutlineCenter + CandidateCenter UI 主流程

### Out of scope (explicit)

- Candidate Knowledge 确认、合并、拆分、发布（Epic 4）
- 目录级检索与模块建议（Epic 5）
- 招标文件评分点、废标项解析
- `candidate_knowledge_stubs` 表结构重构（Epic 4 统一）
- Bid Outline → Template Draft 转换
- 文件夹批量导入

### Epic 依赖

| 依赖 | 用途 |
|------|------|
| Epic 0 Product Category / Chapter Taxonomy | 节点映射、候选规则、模式聚类 |
| Epic 1 File Import + downstream 三条目 | 解析入口、storage_path、分流 |
| Epic 2 Template Chapter（弱） | Chapter Pattern 挖掘样本 |

### Epic 下游

| 消费者 | 输入 |
|--------|------|
| Epic 4 | `candidate_knowledges`（pending）+ `chapter_patterns`（candidate）+ stub 聚合 |
| Epic 5 | `bid_outlines`/`bid_outline_nodes`（confirmed）+ patterns（confirmed，Epic 4 后） |

## Next Step

运行 `/speckit-tasks` 生成 `tasks.md`，再按 TDD 实现 P1 → P2 → P3。
