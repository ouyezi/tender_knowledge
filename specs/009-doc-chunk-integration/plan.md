# Implementation Plan: 实际标书解析接入 doc_chunk

**Branch**: `009-doc-chunk-integration` | **Date**: 2026-06-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-doc-chunk-integration/spec.md`

## Summary

将 Epic 3 实际标书解析流水线（`walk_document` → `extract_toc` → `candidate_generate`）替换为
**doc_chunk 工作区 + 薄适配层落库**，默认启用、可配置回退 legacy。对外 API 与确认向导保持不变；
模板解析路径不改动。依赖同级仓库 `tender_skills` 已验证的 doc_chunk 002/003 能力。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端，本特性无 UI 变更）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, PostgreSQL 15; **新增** `doc-chunk`（path:
`../../tender_skills` editable）; 保留 `python-docx`/`lxml` 供 legacy 分支与 docm 转换

**Reuse**: `actual_bid_parse_runner.py`, `bid_outline_extract_service.py`,
`bid_outline_diff_service.py`, `docm_converter.py`, `chunk_classification_service.py`,
`chapter_candidate_rules.py`, `content_blocks.blocks_v1`

**Storage**: PostgreSQL（实体不变）；临时 doc_chunk 工作区于 `{storage_root}/doc_chunk_workspaces/`

**Testing**: pytest；workspace minimal fixture；legacy 契约回归；可选餐补集成

**Target Platform**: Linux/macOS 开发；Docker Compose

**Project Type**: web-service（backend 改造为主）

**Performance Goals**: 大型标书端到端 ≤ legacy 150%（SC-006）；进度日志持续输出至任务完成

**Constraints**: 人工确认门；Bid Outline 锁定 + diff；单文件导入；无 doc_chunk refine 默认

**Scale/Scope**: 替换 `actual_bid_parse_runner` docx 路径；约 8–12 个新/改服务文件；前端零必需变更

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | spec 009 + 本 plan 后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 仍产出 Tree/Outline/Candidate pending | ✅ | ✅ |
| G3 | Human Confirmation Gate | 候选 pending；outline diff 人工 apply | ✅ | ✅ |
| G4 | Chapter-First & Traceability | linkage→source_node_id；parse_engine 可追溯 | ✅ | ✅ |
| G5 | Retrieval Before Generation | 无检索/生成变更；候选仍隔离 | ✅ | ✅ |
| G6 | MVP Scope | 单文件；无模板/检索范围膨胀 | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/009-doc-chunk-integration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── doc-chunk-import-internal.md
│   └── actual-bid-parse-api-delta.md
├── checklists/requirements.md
└── tasks.md              # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml                    # + doc-chunk path dependency
├── src/
│   ├── config.py                     # + use_doc_chunk_parse, retention, etc.
│   ├── services/
│   │   ├── actual_bid_parse_runner.py    # branch: doc_chunk | legacy
│   │   └── doc_chunk/
│   │       ├── __init__.py
│   │       ├── workspace_manager.py
│   │       ├── pipeline_runner.py
│   │       ├── import_service.py
│   │       ├── blocks_v1.py
│   │       └── mappers/
│   │           ├── document_tree.py
│   │           ├── bid_outline.py
│   │           ├── candidates.py
│   │           └── media_assets.py
│   └── models/
│       └── bid_outline.py            # extract_strategy + doc_chunk if needed
├── tests/
│   ├── fixtures/doc_chunk_workspace_minimal/
│   ├── unit/test_doc_chunk_*.py
│   ├── contract/test_actual_bid_parse_doc_chunk.py
│   └── integration/test_doc_chunk_parse_flow.py

# 保留不删（legacy + template）:
#   docx_document_walker.py, docx_toc_extractor.py, candidate_generate_service.py
```

**Structure Decision**: 新增 `services/doc_chunk/` 包隔离适配逻辑；runner 仅编排分支。

## Complexity Tracking

> 无 Constitution 违规。保留 dual-path（doc_chunk + legacy）为 FR-006 明确要求，非过度工程。

## Phase 0: Research

**Status**: ✅ Complete — see [research.md](./research.md)

要点：path 依赖、import 顺序、linkage 驱动候选、进度映射、工作区生命周期。

## Phase 1: Design

**Status**: ✅ Complete

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Internal import contract | [contracts/doc-chunk-import-internal.md](./contracts/doc-chunk-import-internal.md) |
| API delta | [contracts/actual-bid-parse-api-delta.md](./contracts/actual-bid-parse-api-delta.md) |
| Validation guide | [quickstart.md](./quickstart.md) |

### 实现切片（供 tasks.md）

```text
P0 — 依赖与配置
  T1  pyproject.toml + doc-chunk 可 import
  T2  Settings 开关与 retention

P0 — 核心适配
  T3  workspace_manager + pipeline_runner
  T4  media_assets + document_tree mappers
  T5  bid_outline mapper + diff 兼容
  T6  candidates mapper + blocks_v1 + Preface 过滤
  T7  import_service 编排 + ImportResult

P0 — Runner 集成
  T8  actual_bid_parse_runner doc_chunk 分支
  T9  llm_progress / parse-suggestion 扩展
  T10 unit + contract tests + minimal fixture

P1 — 回归与可选
  T11 legacy flag 回归全套契约
  T12 template parse 冒烟
  T13 可选餐补 integration + quickstart 文档验证
```

## Phase 2: Tasks

由 `/speckit-tasks` 生成 `tasks.md`（本命令不创建）。

## Post-Design Constitution Re-check

所有 Gate 仍通过。设计未引入静默发布、未破坏章节溯源、未扩大 MVP 范围。

## References

- tender_skills: `docs/superpowers/specs/2026-06-15-doc-chunk-tender-knowledge-integration.md`
- tender_skills: `docs/superpowers/specs/2026-06-15-doc-chunk-tk-integration-fixes.md`
- Epic 3 baseline: `specs/004-actual-bid-candidates/`
