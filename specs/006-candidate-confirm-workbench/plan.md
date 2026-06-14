# Implementation Plan: Epic 4 候选知识确认工作台

**Branch**: `006-candidate-confirm-workbench` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/006-candidate-confirm-workbench/spec.md`

## Summary

在 Epic 2/3 已产出 **pending** Candidate Knowledge（document 表 + template stub 聚合）的基础上，
实现 **人工确认 → 编辑 → 合并/拆分/忽略 → 发布为正式知识资产** 全链路治理闭环。
复用 FastAPI + PostgreSQL + React 单体架构；新增 KU/Wiki/Manual Asset 正式表、
`candidate_publish_service` 编排器、批量确认 API、审计日志与 CandidateCenter 可编辑 UI。
发布后保留 `candidate_id` 来源链；未确认候选与 Epic 5 检索严格隔离。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15 (psycopg);
React 18, Ant Design 5, Vite, @ant-design/pro-components

**Reuse from Epic 2/3**:

- `candidates.py` 聚合列表/详情（扩展筛选 + 写路由）
- `candidate_knowledges` / `candidate_knowledge_stubs` 模型
- `template_chapters`, `chapter_patterns`, `product_categories` 正式表
- Epic 2 `template_publish_service` 事务/audit 模式
- Epic 0 分类校验工具

**Storage**: PostgreSQL 15（候选扩展字段 + knowledge_units/wikis/manual_assets +
candidate_confirm_audit_logs）；Epic 1 `STORAGE_ROOT` 只读（Manual Asset 文件型）

**Testing**: pytest + httpx（契约/集成）；Vitest（CandidateCenter UI）；fixtures 复用
Epic 3 pending 候选 seed；publish 幂等与 batch partial failure 用例

**Target Platform**: Linux/macOS 开发；Docker Compose；生产 Linux 容器

**Project Type**: web-service（backend API + admin frontend）

**Performance Goals**: 候选列表 P95 < 500ms（含筛选）；单条 confirm P95 < 2s；
批量 50 条 confirm 汇总 P95 < 30s（SC-006）；审计日志查询 P95 < 1s

**Constraints**: 单文件导入；人工确认门（Constitution G3）；已发布对象不可物理删除；
未确认候选不可检索；MVP 无双人审核/复杂权限；stub 表不重构，适配器统一 API

**Scale/Scope**: 单 KB pending 候选 ~500；单批次批量 ≤100；Epic 4 不含检索实现（Epic 5）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | Epic 4 spec + plan 后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 发布产出 KU/Wiki/Template Chapter 等，非仅改候选 status | ✅ | ✅ |
| G3 | Human Confirmation Gate | pending → confirm API → published；无自动发布 | ✅ | ✅ |
| G4 | Chapter-First & Traceability | candidate_id 来源链 + confirm audit + trace_id | ✅ | ✅ |
| G5 | Retrieval Before Generation | 候选隔离；正式对象 searchable 门；不实现生成 | ✅ | ✅ |
| G6 | MVP Scope | 无文件夹导入、无双人审核、无检索策略优化 | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/006-candidate-confirm-workbench/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── candidate-confirm-api.md
│   ├── candidate-batch-api.md
│   └── candidate-audit-api.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/routes/
│   │   ├── candidates.py              # 扩展 PATCH/confirm/merge/split + 列表筛选
│   │   ├── candidate_batch.py         # batch confirm/reject
│   │   ├── candidate_audit_logs.py    # 审计查询
│   │   ├── knowledge_units.py         # 正式 KU 只读 list/get（Epic 5 前置）
│   │   ├── wikis.py                   # 正式 Wiki 只读
│   │   └── manual_assets.py           # 正式 Manual Asset 只读
│   ├── models/
│   │   ├── candidate_knowledge.py     # 扩展 confirmed/lineage 字段
│   │   ├── candidate_knowledge_stub.py
│   │   ├── knowledge_unit.py          # NEW
│   │   ├── wiki.py                    # NEW
│   │   ├── manual_asset.py            # NEW
│   │   └── candidate_confirm_audit_log.py
│   ├── services/
│   │   ├── candidate_adapter.py       # doc_/tpl_ 双源读写
│   │   ├── candidate_edit_service.py
│   │   ├── candidate_merge_service.py
│   │   ├── candidate_publish_service.py   # 编排器
│   │   ├── candidate_publish_validator.py
│   │   ├── publishers/
│   │   │   ├── ku_publisher.py
│   │   │   ├── wiki_publisher.py
│   │   │   ├── template_chapter_publisher.py
│   │   │   ├── manual_asset_publisher.py
│   │   │   ├── chapter_pattern_publisher.py
│   │   │   ├── product_category_publisher.py
│   │   │   └── ignore_handler.py
│   │   └── candidate_audit_service.py
│   └── main.py
├── tests/
│   ├── contract/test_candidate_confirm*.py
│   ├── contract/test_candidate_batch*.py
│   ├── integration/test_candidate_publish_flow.py
│   └── unit/test_candidate_publish_validator.py
└── alembic/versions/xxxx_epic4_candidate_confirm.py

frontend/
├── src/
│   ├── pages/CandidateCenter/
│   │   ├── index.tsx                  # ProTable 列表 + 筛选
│   │   ├── CandidateDetailDrawer.tsx    # 编辑 + 发布
│   │   ├── CandidateMergeModal.tsx
│   │   ├── CandidateSplitModal.tsx
│   │   └── CandidateAuditPanel.tsx
│   ├── services/
│   │   ├── candidates.ts              # 扩展 confirm/batch API
│   │   └── candidateAudit.ts
│   └── App.tsx                          # /candidates 路由不变
```

**Structure Decision**: 延续 Epic 0–3 monorepo。Publish 编排器 + 类型 publisher 分文件，
避免 `candidate_publish_service` 膨胀。正式 KU/Wiki/Manual Asset 只读 API 供 quickstart
负向测试与 Epic 5 衔接。

## Complexity Tracking

> 无 Constitution 违规项；本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 Output

See [research.md](./research.md) — 双源适配器、publish 编排器、KU/Wiki/Manual Asset 新表、
merge/split lineage、幂等重试、审计表、UI 升级、校验规则均已决议。

## Phase 1 Output

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Confirm API | [contracts/candidate-confirm-api.md](./contracts/candidate-confirm-api.md) |
| Batch API | [contracts/candidate-batch-api.md](./contracts/candidate-batch-api.md) |
| Audit API | [contracts/candidate-audit-api.md](./contracts/candidate-audit-api.md) |
| Validation guide | [quickstart.md](./quickstart.md) |

## Implementation Notes (for tasks.md)

### User Story → Component mapping

| Story | Backend | Frontend |
|-------|---------|----------|
| P1 列表筛选 | `candidates.py` 扩展 query | CandidateCenter ProTable filters |
| P1 编辑详情 | `candidate_edit_service` | CandidateDetailDrawer |
| P1 发布 | `candidate_publish_service` + publishers | 发布面板 confirm_as |
| P2 合并/拆分 | `candidate_merge_service` | Merge/Split Modal |
| P2 批量确认/驳回 | `candidate_batch.py` | 多选 + 结果 Drawer |
| P3 操作日志 | `candidate_audit_logs.py` | CandidateAuditPanel |

### Foundational tasks (blocking)

1. Alembic migration：候选扩展字段 + 三正式表 + audit 表
2. `candidate_adapter` + enum 扩展
3. `candidate_publish_validator` + unit tests
4. Publishers（ku/wiki/template_chapter/manual_asset/chapter_pattern/product_category/ignore）
5. `candidate_publish_service` 幂等 + retry
6. PATCH/confirm/merge/split routes + contract tests
7. Batch confirm/reject + audit batch header
8. Audit log list API
9. KU/Wiki/Manual Asset 只读 GET（来源追溯验收）
10. CandidateCenter UI 全流程

### Out of scope (explicit)

- 实际标书/模板解析（Epic 2/3）
- 向量检索与 retrieval_trace（Epic 5）
- 模块组织建议与生成辅助（Epic 6）
- 双人审核、角色权限
- stub → 主表一次性迁移

### Epic 依赖

| 依赖 | 用途 |
|------|------|
| Epic 0 Product Category / Chapter Taxonomy | 发布校验、分类字段 |
| Epic 2 Template + stub | template 通道候选、template_chapter 发布 |
| Epic 3 candidate_knowledges | document 通道候选、KU 来源链 |

### Epic 下游

| 消费者 | 输入 |
|--------|------|
| Epic 5 | knowledge_units, wikis, manual_assets, confirmed chapter_patterns, published template_chapters |
| Epic 6 | 同上 + searchable 门 |

## Next Step

运行 `/speckit-tasks` 生成 `tasks.md`，再交由 Superpowers TDD 实现。
