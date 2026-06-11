# Implementation Plan: Epic 0 分类底座

**Branch**: `001-classification-base` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-classification-base/spec.md`

## Summary

建立 V3.0 前置「分类底座」：在知识库内提供 **Product Category**（产品分类树）与
**Chapter Taxonomy**（章节分类体系）的完整治理能力，含别名/同义名、生命周期
（启用/停用/归档/合并）、影响分析与审计 trace。采用 FastAPI + PostgreSQL 后端与
React 管理后台；Epic 1 通过 REST 读接口消费 active 分类列表。

## Technical Context

**Language/Version**: Python 3.11（后端）、TypeScript 5.x（前端）

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, PostgreSQL 15 driver (psycopg), React 18, Ant Design 5, Vite

**Storage**: PostgreSQL 15（邻接表 + materialized path 树；audit log；classification_reference）

**Testing**: pytest, httpx (API contract/integration), pytest-asyncio；前端 Vitest + Playwright（UI 冒烟）

**Target Platform**: Linux/macOS 开发；Docker Compose 本地部署；生产 Linux 容器

**Project Type**: web-service（backend API + admin frontend）

**Performance Goals**: 影响分析 API P95 < 3s（单分类 ≤10k 引用，SC-003）；分类树查询 P95 < 500ms（≤500 节点/KB）

**Constraints**: kb 级隔离；无物理删除；合并必须事务一致；V3.0 无 RBAC（X-Operator-Id 审计）

**Scale/Scope**: 单 KB 产品分类 ~200 节点、章节分类 ~300 节点；Epic 0 不含检索/生成/导入

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Reference: `.specify/memory/constitution.md`

| Gate | Principle | Pass Criteria | Pre-Design | Post-Design |
|------|-----------|---------------|------------|-------------|
| G1 | Spec-Driven Delivery | Epic 0 spec + plan 完成后再编码 | ✅ | ✅ |
| G2 | Knowledge Asset First | 产出 Product Category / Chapter Taxonomy 知识层资产 | ✅ | ✅ |
| G3 | Human Confirmation Gate | binding.source 预留 manual>suggested；无静默发布 | ✅ | ✅ (R8 schema 预留) |
| G4 | Chapter-First & Traceability | Chapter Taxonomy + audit trace_id 全写操作 | ✅ | ✅ |
| G5 | Retrieval Before Generation | 提供按产品/章节过滤的读 API；Epic 0 无生成 | ✅ | ✅ |
| G6 | MVP Scope | 无文件夹导入、检索推荐、候选工作台、RBAC | ✅ | ✅ |

**Status**: [x] G1 [x] G2 [x] G3 [x] G4 [x] G5 [x] G6 — all pass

## Project Structure

### Documentation (this feature)

```text
specs/001-classification-base/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   ├── knowledge-base-api.md
│   ├── product-category-api.md
│   └── chapter-taxonomy-api.md
└── tasks.md             # 见 docs/superpowers/plans/
```

### Source Code (repository root)

```text
backend/
├── alembic/
│   └── versions/
├── src/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── product_categories.py
│   │   │   └── chapter_taxonomies.py
│   │   └── deps.py
│   ├── models/
│   │   ├── knowledge_base.py
│   │   ├── product_category.py
│   │   ├── chapter_taxonomy.py
│   │   ├── classification_reference.py
│   │   └── audit_log.py
│   ├── schemas/
│   ├── services/
│   │   ├── category_tree.py
│   │   ├── impact_analysis.py
│   │   └── merge.py
│   └── main.py
├── tests/
│   ├── contract/
│   ├── integration/
│   └── unit/
├── scripts/
│   ├── seed_kb.py
│   └── seed_classification_references.py
├── alembic.ini
└── startup.py

frontend/
├── src/
│   ├── pages/
│   │   ├── ProductCategoryCenter/
│   │   └── ChapterTaxonomyCenter/
│   ├── services/
│   └── App.tsx
└── tests/

docker-compose.yml
scripts/                 # start.sh / stop.sh / restart.sh
```

**Structure Decision**: Monorepo web 应用（Option 2）。Epic 0 同时交付 API 与管理后台
两个中心页面；backend/frontend 分离便于 Epic 1 复用 API。

## Implementation Status (2026-06-11)

| Slice | Status | Notes |
|-------|--------|-------|
| P0 多 KB 壳层 | ✅ | CRUD、clone、KB 切换 UI |
| P1 产品分类 | ✅ | 树/别名/搜索/生命周期 API + UI |
| P2 章节分类 | ✅ | 同义名/M:N 绑定 API + UI |
| P3 生命周期 | ✅ | impact、merge、audit、UI 向导 |
| Alembic 迁移 | ⏳ | 当前 `init_db.create_all`；迁移待补 |

验收指南：[quickstart.md](./quickstart.md)

## Complexity Tracking

> 无 Constitution 违规项；本表留空。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 Output

See [research.md](./research.md) — 技术栈、树存储、别名唯一、影响分析引用表、合并语义均已决议。

## Phase 1 Output

| Artifact | Path |
|----------|------|
| Data model | [data-model.md](./data-model.md) |
| Product Category API | [contracts/product-category-api.md](./contracts/product-category-api.md) |
| Chapter Taxonomy API | [contracts/chapter-taxonomy-api.md](./contracts/chapter-taxonomy-api.md) |
| Validation guide | [quickstart.md](./quickstart.md) |

## Implementation Notes (for tasks.md)

### User Story → Component mapping

| Story | Backend | Frontend |
|-------|---------|----------|
| P1 产品分类树 | `product_categories` routes, tree service | ProductCategoryCenter |
| P2 章节分类 | `chapter_taxonomies` routes, binding | ChapterTaxonomyCenter |
| P3 生命周期/影响 | impact + merge services, audit | 影响分析弹窗、合并向导 |

### Foundational tasks (blocking)

1. docker-compose + PostgreSQL + Alembic baseline
2. Knowledge Base + Product Category + Chapter Taxonomy models/migrations
3. Audit log middleware (`trace_id`, `X-Operator-Id`)
4. classification_reference table (empty OK for Epic 0)

### Out of scope (explicit)

- Bid Outline / Template Chapter 自动发现（Epic 2/3）
- 检索、模块建议、生成辅助 API
- 角色权限
- 文件夹/批量导入

## Next Step

- Epic 1：消费 active 分类读接口；写入 `classification_reference`
- 补齐 Alembic baseline 迁移
- 可选：Playwright UI 冒烟纳入 CI
