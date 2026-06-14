# Implementation Plan: 标书目录提取质量增强

**Branch**: `005-outline-extraction-quality` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-outline-extraction-quality/spec.md`

## Summary

在 Epic 3 已落地的两阶段层级推断（`content_heuristic`）与 `parent_id` 落库修复基础上，借鉴
`tender_doctor` 的 **structural_only 过滤**、**heading 栈质量评估** 与 **单一推断事实来源** 思路，
新增规则层过滤伪标题、计算目录质量摘要，并收敛 `walk_document` 与 `extract_toc_entries` 的双路径推断。

技术路线：**不引入 LLM**；在 `docx_toc_extractor` / `actual_bid_parse_runner` 流水线中插入
`outline_heading_filter` + `outline_quality_service`；质量摘要写入 `document_parse_suggestion.payload`
与解析任务 API；前端目录中心/确认向导只读展示摘要与警告。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, PostgreSQL 15, python-docx, lxml；React 18, Ant Design 5, Vite

**Reuse from Epic 3 / 层级推断**:
`docx_content_collector`, `docx_hierarchy_inferrer`, `docx_tree_materializer`,
`heading_level_detector`, `docx_document_walker`, `docx_toc_extractor`,
`bid_outline_extract_service`, `actual_bid_parse_runner`

**Reference (read-only)**: `tender_doctor` — `section_tree.py`（栈建树）、`chunking._resolve_section_heading`、
`markdown_body.effective_body_text`、`layout_quality.assess_layout_quality`

**Storage**: PostgreSQL 15；质量摘要与过滤统计存于 `document_parse_suggestions.payload`（JSON 扩展字段）；
不新增表（MVP）。`document_tree_nodes` 沿用 `is_outline_node`、`needs_manual_review`；
过滤原因写入 parse suggestion 的 `filter_stats` 映射。

**Testing**: pytest 单元（filter rules、quality metrics、统一推断）；集成（`actual_bid_parse_runner` 端到端）；
回归 fixture：鼎信餐补标书 + `backend/tests/fixtures/` 小型 docx；真章节基准 JSON（≥20 条标题）

**Target Platform**: Linux/macOS 开发；与现有 `./scripts/start.sh` 一致

**Project Type**: web-service（backend API + admin frontend 轻量扩展）

**Performance Goals**: 过滤与质量计算 O(n) 单次遍历；对 200MB docm 增量耗时 <10%（SC-005）；
质量摘要 API 字段随既有 task/outline GET 返回，无额外 round-trip

**Constraints**: 无 LLM；TOC 策略优先级不变；被过滤段落保留在 Document Tree；
Bid Outline 为过滤后子集；人工确认闸门不变；`ready` 任务过滤规则与 P0 一致

**Scale/Scope**: 单文档 outline 节点数百级；过滤规则配置 YAML/Python 常量；前端 2 页面轻改
（`OutlineCenter/index.tsx`、`ActualBidParseConfirmWizard.tsx`）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | Epic 3 子特性 spec + plan 后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 提升 Bid Outline 资产质量，非文件存储 | ✅ | ✅ |
| G3 | Human Confirmation Gate | 过滤不进默认 Outline；Document Tree 保留；确认向导可编辑 | ✅ | ✅ |
| G4 | Chapter-First & Traceability | filter_reason + quality 摘要可追溯至 parse_task | ✅ | ✅ |
| G5 | Retrieval Before Generation | 目录质量支撑「先治理再检索」；无生成能力变更 | ✅ | ✅ |
| G6 | MVP Scope | 单文件 docx/docm；无 LLM reorg；无 PDF | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/005-outline-extraction-quality/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── outline-quality-api.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── config/
│   │   └── outline_filter_rules.yaml     # NEW: 阈值与模式配置
│   ├── services/
│   │   ├── outline_heading_filter.py     # NEW: structural_only / date / body_list
│   │   ├── outline_quality_service.py    # NEW: 质量摘要 + 警告标志
│   │   ├── outline_text_utils.py         # NEW: effective_body_text（借鉴 tender_doctor）
│   │   ├── docx_toc_extractor.py         # MOD: 接受 walk 快照；过滤后 entries
│   │   ├── docx_document_walker.py       # MOD: 导出 collected+inferred 快照
│   │   ├── bid_outline_extract_service.py # MOD: 过滤统计透传
│   │   └── actual_bid_parse_runner.py    # MOD: 单次推断；写 quality 到 suggestion
│   ├── api/routes/
│   │   ├── actual_bid_parse.py           # MOD: task 响应含 outline_quality
│   │   └── bid_outlines.py               # MOD: list 项含 quality 摘要（可选）
│   └── tests/
│       ├── unit/
│       │   ├── test_outline_heading_filter.py
│       │   ├── test_outline_quality_service.py
│       │   └── test_outline_unified_infer.py
│       ├── integration/
│       │   └── test_actual_bid_outline_quality.py
│       └── fixtures/
│           ├── dingxin-golden-titles.json  # 真章节基准
│           └── sample-noisy-outline.docx
frontend/
├── src/
│   ├── pages/OutlineCenter/
│   │   ├── index.tsx                     # MOD: 待办显示质量摘要
│   │   └── ActualBidParseConfirmWizard.tsx # MOD: 质量警告 Alert
│   └── services/actualBidParse.ts        # MOD: 类型扩展
```

**Structure Decision**: 延续 Epic 3 monorepo；新增服务模块置于 `backend/src/services/`，
配置与 `chapter_candidate_rules.yaml` 并列；不新增 DB 表，降低迁移风险。

## Complexity Tracking

> 无 Constitution 违规项；本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 Output

See [research.md](./research.md) — tender_doctor 借鉴点、统一推断方案、过滤规则分级、
质量阈值、无新表 JSON 载荷设计、鼎信回归基准。

## Phase 1 Output

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| API contracts | [contracts/outline-quality-api.md](./contracts/outline-quality-api.md) |
| Quickstart | [quickstart.md](./quickstart.md) |

### Design Decisions (Post Phase 1)

1. **单一推断快照**：`walk_document` 返回 `CollectedContent + InferResult`；`extract_toc_entries`
   新增 `extract_toc_from_infer_snapshot(...)`，TOC XML 命中时仍走 XML 路径且不二次 `collect_content`。
2. **过滤作用点**：在物化 `OutlineNode[]` 之后、`persist_outline` 之前过滤；Document Tree 仍写入全部
   `is_outline_node=true` 的 heading，但 `persist_outline` 仅接收 `action=keep` 的条目。
3. **质量摘要**：`outline_quality_service.summarize(entries, strategy, filter_stats)` → 写入
   `document_parse_suggestion.payload.outline_quality`；任务 GET 透传。
4. **警告阈值**（A-004）：`l1_ratio > 0.6 && node_count > 30`；`review_ratio > 0.4`；
   `extract_strategy == flat_fallback` 恒警告。

## Phase 2

由 `/speckit-tasks` 生成 `tasks.md`（本命令不创建）。
