# Tasks: Epic 3 + 005 联合收尾

**Input**: `docs/superpowers/specs/2026-06-14-epic3-005-completion-design.md`  
**Detailed plan**: `docs/superpowers/plans/2026-06-14-epic3-005-completion.md`

**Prerequisites**: Epic 0/1 已交付；004 主体代码已存在

**Tests**: TDD — 每 Task 先写失败测试再实现（见 detailed plan）

## Format: `[ID] [Phase] Description`

---

## Phase 1: 流水线稳定（阻塞）

- [x] T001 [P1] Task 1 — `walk_document` text fallback 完整 infer snapshot + 单测
- [x] T002 [P1] Task 2 — `extract_toc_entries` 残缺 snapshot 安全降级 + 单测
- [x] T003 [P1] Task 3 — 集成测 fixture 对齐 `sample-actual-bid.docx`
- [x] T004 [P1] Task 4 — Phase 1 Epic3 相关 pytest 批跑全绿

**Checkpoint**: `test_actual_bid_flow` + `test_bid_outline_structure_diff` 通过

---

## Phase 2: 005 质量门禁

- [x] T005 [P2] Task 5 — `dingxin-baseline-stats.json` + 离线 golden/减节点测
- [x] T006 [P2] Task 6 — `test_bid_outline_parent_id.py` 非根 parent_id ≥70%
- [x] T007 [P2] Task 7 — 核对 reason_code payload + ready 列表不含 failed

**Checkpoint**: dingxin 离线测 + parent_id 测通过

---

## Phase 3: 004 UI + 文档

- [x] T008 [P3] Task 8 — `actualBidParse.ts` progress/logs 类型扩展
- [x] T009 [P3] Task 9 — `ParseTaskLogDrawer` + OutlineCenter（移除新建目录、failed 任务）
- [x] T010 [P3] Task 10 — 更新 004/005 spec + quickstart
- [x] T011 [P3] Task 11 — 最终验收批跑 + tasks 勾选

**Checkpoint**: 统一验收门禁（design doc）全部满足

---

## Out of Scope（本 tasks 不做）

- LLM 章节分类（FR-022 推迟 Epic 4）
- Document Tree PATCH API
- 「新建目录」功能
- 前端 Vitest
- Epic 5 检索 / SC-006 运行时验证

---

## Dependencies

| 依赖 | 用途 |
|------|------|
| Epic 0 | Chapter Taxonomy / Product Category |
| Epic 1 | File Import + downstream |
| 005 模块（已部分落地） | filter / quality / embedded detector |
