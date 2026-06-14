# Epic 3 + 005 联合收尾设计

**Date**: 2026-06-14  
**Status**: Implemented (2026-06-14)  
**Scope**: `specs/004-actual-bid-candidates` + `specs/005-outline-extraction-quality`

## 背景

Epic 3（实际标书导入与候选知识）主体功能已实现（约 85–90%），但存在：

1. **005 目录质量重构**与 004 解析流水线集成不完整，导致 3 个集成测试失败（`infer_snapshot missing infer_result or collected`）。
2. **005** 过滤规则、质量指标、前端展示已部分落地，鼎信 golden 回归测仍为 skip。
3. **004** 若干 plan 项未交付或需按决策调整（ParseTaskLogPanel、新建目录、LLM 分类、Document Tree 编辑）。

本设计在 brainstorming 中确认：**004 + 005 一并收尾，统一验收**。

## 决策记录

| 维度 | 选择 | 说明 |
|------|------|------|
| 总范围 | **C** | 004 + 005 联合完成并统一验收 |
| 章节分类 LLM（004 FR-022） | **B** | 规则-only；LLM 推迟 Epic 4 或后续特性 |
| Document Tree 编辑（004 US3） | **A** | Document Tree 只读追溯；分类映射以 Bid Outline 为准 |
| 任务日志 UI（004 US6） | **A** | 目录中心待办表 + Drawer/可展开行，不建独立页面 |
| 「新建目录」按钮 | **A** | 移除 stub；功能推迟 |
| 实现策略 | **统一推断快照 + 分阶段交付** | 技术上收敛 walk/extract；交付分三阶段验收 |

## 架构：解析流水线

### 目标

单次解析内，Document Tree 与 Bid Outline 来自 **同一份推断快照**；任何降级路径不得抛出 `infer_snapshot missing`，失败任务不得进入 `ready` 待确认列表（005 FR-012）。

### 数据流

```text
docx 文件
  → walk_document() → DocumentWalkResult
       ├─ nodes[]           → persist Document Tree
       ├─ infer_result      ─┐
       └─ collected.blocks  ─┴→ extract_toc_entries(snapshot)
                                    → outline_heading_filter
                                    → outline_quality_service
                                    → persist Bid Outline
  → candidate_generate_service（规则-only）
  → task.status = ready
```

### 关键修复

1. **`walk_document` text fallback**：docx 打不开时仍产出完整快照（`collect_content` + `infer_hierarchy` 或等价最小 blocks），填充 `infer_result` 与 `collected`。
2. **`extract_toc_entries`**：消费完整 `DocumentWalkResult`；禁止在 snapshot 字段缺失时抛异常（优先修 walker，而非 runner 传残缺 snapshot）。
3. **测试 fixture**：修复 `uploaded_need_confirm` 集成路径中 storage 落盘与 runner 读取路径不一致导致的 `Package not found`。
4. **失败隔离**：解析异常 → `status=failed` + `error_message`；列表 API 与待确认区不展示脏 `ready` 任务。

### 明确不做

- LLM 目录纠偏（005 A-001）
- LLM 章节分类建议（004 FR-022 本阶段）
- Document Tree PATCH API
- 独立 ParseTaskLogPanel 页面
- 「新建目录」功能
- 前端 Vitest（推迟）

## 005 剩余交付

### 已完成（工作区）

| 能力 | 模块 |
|------|------|
| 标题过滤规则 | `outline_heading_filter.py`, `outline_filter_rules.yaml` |
| 质量摘要 | `outline_quality_service.py` |
| 内嵌附件检测 | `embedded_document_detector.py` |
| Runner 接入 filter/quality | `actual_bid_parse_runner.py` |
| 确认向导展示 | `ActualBidParseConfirmWizard.tsx` |
| 目录中心质量列 | `OutlineCenter/index.tsx` |

### 待完成

**P1 — 流水线闭环**

- [ ] 统一快照修复覆盖 toc / heuristic / flat_fallback 全路径
- [ ] 过滤 `reason_code` 写入 `DocumentParseSuggestion.payload`（核对 FR-003）
- [ ] 失败任务不进入 `ready` 待确认（FR-012 / SC-006）

**P1 — 鼎信回归（FR-011, SC-001, SC-004）**

- [ ] 完善 `backend/tests/fixtures/dingxin-golden-titles.json`（≥20 条）
- [ ] 离线集成/单元测：golden 保留率 ≥95%；节点数较 baseline 减少 ≥30%
- [ ] 可选：`DINGXIN_DOCM` 环境变量本地 E2E（CI skip）

**P2 — 层级与性能**

- [ ] 集成测：样例 docx 非根节点 ≥70% 有 `parent_id`（FR-006）
- [ ] 确认 `OutlineDetailPage` 树展示与 API `level`/`parent_id` 一致
- [ ] 质量/过滤 O(n)，无额外全文扫描（SC-005，code review）

## 004 UI 收尾

### 目录中心 `OutlineCenter/index.tsx`

1. **移除**「新建目录」disabled 按钮。
2. **新增**任务日志 Drawer：待办表「查看日志」→ `GET /tasks/{id}`，展示：
   - `llm_progress.logs`（阶段时间线）
   - `phase_timings_ms`
   - `outline_quality`、`filtered_total`、过滤样本
   - `downstream_entries`
   - 失败时 `error_message`
3. **展示失败任务**：同表或筛选 `failed`，红色 Tag + 日志入口。

### 前端类型

`actualBidParse.ts` 扩展 `llm_progress`：

```typescript
logs?: Array<{ ts: string; level: string; message: string }>;
phase_timings_ms?: Record<string, number>;
```

### 不变

- `ActualBidParseConfirmWizard` — 质量/过滤只读
- `OutlineDetailPage` — 树编辑、diff、确认目录
- `CandidateCenter` — 只读，无确认/发布

## 文档更新

| 文件 | 动作 |
|------|------|
| `specs/004-actual-bid-candidates/spec.md` | Assumptions：Document Tree 只读；FR-022 LLM 推迟；日志 UI 为 Drawer |
| `specs/005-outline-extraction-quality/spec.md` | 联合验收说明；004 流水线修复为依赖 |
| `specs/004-actual-bid-candidates/quickstart.md` | 统一验收步骤 + dingxin 测命令 |
| `specs/004-actual-bid-candidates/tasks.md` | Implementation 阶段由 writing-plans 生成 |

## 分阶段交付

### 阶段 1 — 流水线稳定（阻塞）

- 统一快照修复
- 3 个失败集成测恢复通过
- `test_actual_bid_parse_runner` 等契约测保持绿

### 阶段 2 — 005 质量门禁

- dingxin golden 离线测
- reason_code / ready 列表隔离
- parent_id 集成测

### 阶段 3 — 004 UI + 文档

- 目录中心 Drawer + 移除新建目录
- spec/quickstart 同步
- quickstart 场景 0–7 手工走通

## 统一验收门禁

```text
后端
 □ Epic3 + OutlineQuality 相关 pytest 全通过
 □ dingxin golden 离线测：保留率 ≥95%，节点减少 ≥30%
 □ E2E：confirm → parse → ready → wizard → outline lock
 □ 重解析 locked outline：仅 diff，不静默覆盖

前端
 □ 目录中心：待办 + 日志 Drawer，无「新建目录」
 □ 确认向导：质量摘要 + 过滤只读
 □ 候选中心：只读 + 来源追溯

文档
 □ 本设计 doc + spec assumptions 已同步
 □ quickstart 可复现
```

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| walker fallback 仍不完整 | 单元测覆盖 text fallback + 集成测覆盖 upload 路径 |
| 过滤过严删真章节 | dingxin golden SC-004 ≥95% 保留率 |
| 004/005 spec 与实现漂移 | 联合验收前更新 Assumptions，tasks.md 映射 FR |

## 下一步

用户 review 本设计 doc 无误后，运行 **writing-plans** 生成 `docs/superpowers/plans/2026-06-14-epic3-005-completion.md` 及 `specs/004-actual-bid-candidates/tasks.md`，再按 TDD 执行。
