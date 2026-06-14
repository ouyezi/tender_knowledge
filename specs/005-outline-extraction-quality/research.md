# Research: 标书目录提取质量增强

**Date**: 2026-06-14  
**Feature**: `specs/005-outline-extraction-quality`

## R1: tender_doctor 可借鉴点

### Decision

采纳三项规则层能力，**不**采纳 LLM refine/reorg 链。

| 借鉴项 | tender_doctor 来源 | tender_knowledge 落地 |
|--------|-------------------|----------------------|
| structural_only | `markdown_body.effective_body_text` + `section_tree` | `outline_text_utils.effective_body_text`；无正文则标记 `structural_only` |
| heading 栈质量启发式 | `layout_quality.assess_layout_quality` | `outline_quality_service` 计算 l1_ratio、max_depth、orphan 近似指标 |
| 单一事实来源 | Block → chunk → section_tree 一条链 | `walk_document` 产出推断快照，`extract` 复用同一快照 |

### Rationale

鼎信样例问题来自规则过宽（正文编号变标题），非缺 LLM。tender_doctor 在无 Heading 样式文档上
也依赖规则 baseline + 可选 LLM；本特性宪法与 spec 明确排除 LLM，规则过滤是 ROI 最高路径。

### Alternatives considered

- **全量移植 chunk_layout LLM**：拒绝——违反 A-001，延迟与审计成本高。
- **仅前端隐藏噪声节点**：拒绝——不减少确认向导负担，且 API/检索仍暴露脏数据。
- **硬编码鼎信规则**：拒绝——不可维护；采用可配置模式 + 通用启发式。

---

## R2: 统一 walk 与 extract 推断路径

### Decision

在 `actual_bid_parse_runner._run_entry` 中：

1. `walked = walk_document(path)` — 已含 `infer_result`。
2. Phase 2 改为 `extract_toc_entries(path, infer_snapshot=walked)`：
   - 若 Word TOC XML 命中 → 仍用 `_extract_toc_entries_from_docx_xml`（不重复 infer）。
   - 否则 → `materialize_outline_nodes(walked.infer_result, walked.collected.blocks)`，
     **禁止**再次 `collect_content` + `infer_hierarchy`。

`DocumentWalkResult` 扩展字段：`collected: CollectedContent | None`。

### Rationale

当前 `extract_toc_entries` 独立调用 `_to_fallback_entries` 会二次全文采集与推断，存在性能浪费
与理论上的不一致风险（虽同一文件通常结果相同）。

### Alternatives considered

- **extract 完全弃用，walk 直接产 toc**：拒绝——破坏 TOC 优先策略独立入口与单测边界。
- **共享进程内 LRU 缓存按 path**：拒绝——隐式、难测试；显式快照更清晰。

---

## R3: 伪标题过滤规则分级

### Decision

新增 `outline_heading_filter.py`，对每个 `OutlineNode` / `TocEntry` 输出 `HeadingFilterDecision`：

| reason_code | 条件（初版） | action |
|-------------|-------------|--------|
| `toc_native` | 来自 Word TOC XML 策略 | `keep`（豁免过滤） |
| `heading_style_high` | `heading_level_detector.confidence=high` | `keep` |
| `date_line` | 匹配中日历日期短行（≤40 字，含年月日） | `exclude` |
| `body_list_item` | `numeric` pattern + 标题长度 >80 + level≤2 + 父上下文为函件类 | `exclude` |
| `structural_only` | heading 后无 effective_body（段落下一段非 table 且为空） | `exclude` |
| `default` | 其他 medium 置信度中文编号 | `keep` + `needs_manual_review=true` |

父上下文：利用 `parent_temp_id` / 栈顶标题关键词（参选响应函、承诺、声明）。

配置：`backend/src/config/outline_filter_rules.yaml`（阈值、关键词列表可热更新）。

### Rationale

分阶段降低误杀：高置信度样式与 TOC 豁免；先处理鼎信最明显噪声（日期、长句列举）。

### Alternatives considered

- **全部 medium 编号 exclude**：拒绝——误杀「一、报价表格式」等真章节（违反 SC-004）。
- **过滤在 inferrer 内**：拒绝——推断与过滤职责分离，便于单测与 TOC 豁免。

---

## R4: 质量摘要存储与 API 透传

### Decision

**不新增表**。扩展 `document_parse_suggestions.payload`：

```json
{
  "outline_quality": {
    "node_count": 120,
    "max_depth": 4,
    "l1_ratio": 0.42,
    "needs_manual_review_count": 15,
    "extract_strategy": "content_heuristic",
    "warnings": ["high_l1_ratio"],
    "filter_stats": { "excluded": 180, "kept": 120, "by_reason": { "body_list_item": 90 } }
  }
}
```

`GET .../actual-bid-parse/tasks/{id}` 与 `GET .../actual-bid-parse/tasks?status=ready` 的 item
增加 `outline_quality`（从 suggestion 联接或 task 缓存字段读取）。

`bid-outlines` 列表项可选增加 `outline_quality` 摘要（同 document 最新 parse）。

### Rationale

质量数据随解析任务产生，与 Epic 3 `DocumentParseSuggestion` 语义一致；避免 migration。

### Alternatives considered

- **新表 `outline_quality_summaries`**：拒绝——MVP 过重，JSON 足够。
- **仅写 llm_progress**：拒绝——llm_progress 偏运行时日志，不宜作为产品只读摘要源。

---

## R5: 鼎信回归基准

### Decision

登记 `backend/tests/fixtures/dingxin-golden-titles.json`（≥20 条真章节标题）与基线节点数
（增强前约 432 → 目标 ≤302 且 golden 保留率 ≥95%）。

集成测试 `test_actual_bid_outline_quality.py` 在具备本地鼎信 docm 路径时跑 full；
CI 使用缩小版 `sample-noisy-outline.docx` fixture。

### Rationale

满足 FR-011 / SC-001 / SC-004 的可执行门禁。

### Alternatives considered

- **仅手工验收**：拒绝——无法回归 parent_id/过滤改动。

---

## R6: 前端展示范围

### Decision

- **目录中心待办表**：增加列「节点数 / L1% / 警告」；文件名替代部分 UUID（P1 体验，本特性一并纳入）。
- **确认向导 Step 0/1**：若 `warnings` 非空，顶部 `Alert` 展示建议文案。
- **不**改 `OutlineTreeEditor` 为树形（留待后续 UX Epic）。

### Rationale

满足 FR-005、FR-010、A-005；最小 diff 达成 SC-003（10 秒内判断质量）。

---

## Open Questions (resolved)

| 问题 | 决议 |
|------|------|
| 过滤节点是否进 Document Tree？ | 进，作为 heading/paragraph；仅 Bid Outline 排除 |
| 阈值是否可配置？ | 是，`outline_filter_rules.yaml` |
| 模板库是否同步？ | 否（A-006）；接口设计可复用 |
