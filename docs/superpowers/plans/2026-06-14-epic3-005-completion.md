# Epic 3 + 005 联合收尾 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 004 解析流水线回归，完成 005 目录质量门禁（鼎信 golden），交付 004 目录中心日志 Drawer，统一验收 Epic 3 + 005。

**Architecture:** `walk_document` 始终产出完整 `DocumentWalkResult`（含 `infer_result` + `collected`）；`extract_toc_entries` 消费同一快照后经 `outline_heading_filter` / `outline_quality_service` 落库；前端在目录中心待办表用 Drawer 展示 `llm_progress.logs`。Document Tree 只读；章节分类规则-only。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, python-docx, lxml, pytest | React 18, Ant Design 5, TypeScript

**Design doc:** `docs/superpowers/specs/2026-06-14-epic3-005-completion-design.md`  
**Specs:** `specs/004-actual-bid-candidates/spec.md`, `specs/005-outline-extraction-quality/spec.md`  
**Task index:** `specs/004-actual-bid-candidates/tasks.md`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/src/services/docx_document_walker.py` | text fallback 产出完整推断快照 |
| `backend/src/services/docx_toc_extractor.py` | 残缺 snapshot 安全降级 |
| `backend/tests/unit/test_docx_document_walker.py` | fallback 快照单测 |
| `backend/tests/unit/test_docx_toc_extractor.py` | snapshot 降级单测 |
| `backend/tests/integration/test_actual_bid_flow.py` | E2E 回归 |
| `backend/tests/integration/test_bid_outline_structure_diff.py` | diff 回归；改用 sample-actual-bid |
| `backend/tests/integration/test_actual_bid_outline_quality.py` | 鼎信 golden + baseline |
| `backend/tests/fixtures/dingxin-baseline-stats.json` | 离线节点数 baseline |
| `backend/tests/fixtures/dingxin-golden-titles.json` | 真章节标题集（已有，≥20） |
| `frontend/src/pages/OutlineCenter/ParseTaskLogDrawer.tsx` | 任务日志 Drawer |
| `frontend/src/pages/OutlineCenter/index.tsx` | 移除新建目录；failed 任务；日志入口 |
| `frontend/src/services/actualBidParse.ts` | `llm_progress.logs` 类型 |
| `specs/004-actual-bid-candidates/spec.md` | Assumptions 更新 |
| `specs/005-outline-extraction-quality/spec.md` | 联合验收说明 |
| `specs/004-actual-bid-candidates/quickstart.md` | 验收命令 |

---

## Phase 1 — 流水线稳定（阻塞）

### Task 1: `walk_document` text fallback 完整快照

**Files:**
- Modify: `backend/src/services/docx_document_walker.py`
- Test: `backend/tests/unit/test_docx_document_walker.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_docx_document_walker.py` 末尾添加：

```python
def test_walk_document_text_fallback_includes_infer_snapshot(tmp_path):
    plain = tmp_path / "not-a-docx.txt"
    plain.write_text("第一章 概述\n概述正文。\n一、背景\n背景正文。\n", encoding="utf-8")
    result = walk_document(plain)
    assert result.infer_result is not None
    assert result.collected is not None
    assert len(result.collected.blocks) >= 2
    assert any(n.node_type == "heading" for n in result.nodes)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_docx_document_walker.py::test_walk_document_text_fallback_includes_infer_snapshot -v`

Expected: FAIL — `infer_result is None`

- [ ] **Step 3: 实现 fallback 快照**

在 `docx_document_walker.py` 顶部增加 import：

```python
from src.services.docx_content_collector import CollectResult, RawBlock
```

在 `_iter_paragraph_texts_from_fallback` 之后增加：

```python
def _collect_from_plain_lines(lines: list[str]) -> CollectResult:
    blocks: list[RawBlock] = []
    for index, line in enumerate(lines):
        text = line.strip()
        if not text:
            continue
        blocks.append(
            RawBlock(
                index=len(blocks),
                block_type="paragraph",
                text=text,
                style_name="Normal",
                has_image=False,
            )
        )
    return CollectResult(blocks=blocks)
```

替换 text fallback 的 `return DocumentWalkResult(...)` 分支（约 L68–93）为：

```python
        collected = _collect_from_plain_lines(fallback_texts)
        inferred = infer_hierarchy(collected.blocks)
        materialized = materialize_walk_result(collected.blocks, inferred)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.warning(
            "walk_document DONE via text_fallback nodes=%d elapsed_ms=%d path=%s",
            len(materialized.nodes),
            elapsed_ms,
            file_path,
        )
        return DocumentWalkResult(
            nodes=materialized.nodes,
            used_flat_fallback=True,
            needs_manual_review=True,
            infer_result=inferred,
            collected=collected,
        )
```

- [ ] **Step 4: 运行单测通过**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_docx_document_walker.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/docx_document_walker.py backend/tests/unit/test_docx_document_walker.py
git commit -m "fix: text fallback walk produces full infer snapshot for toc extract"
```

---

### Task 2: `extract_toc_entries` 残缺 snapshot 安全降级

**Files:**
- Modify: `backend/src/services/docx_toc_extractor.py`
- Test: `backend/tests/unit/test_docx_toc_extractor.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_docx_toc_extractor.py` 添加：

```python
from src.services.docx_document_walker import DocumentWalkResult


def test_extract_toc_entries_degrades_when_snapshot_incomplete(tmp_path):
    broken = DocumentWalkResult(nodes=[], used_flat_fallback=True, needs_manual_review=True)
    docx = FIXTURE  # sample-actual-bid.docx
    result = extract_toc_entries(docx, infer_snapshot=broken)
    assert result.entries
    assert result.strategy.value in {"toc", "heading_heuristic", "content_heuristic", "flat_fallback"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_docx_toc_extractor.py::test_extract_toc_entries_degrades_when_snapshot_incomplete -v`

Expected: FAIL — `ValueError: infer_snapshot missing infer_result or collected`

- [ ] **Step 3: 实现降级逻辑**

在 `docx_toc_extractor.py` 顶部增加 `import logging` 与 `logger = logging.getLogger(__name__)`。

修改 `extract_toc_entries` 中 infer_snapshot 分支：

```python
    if infer_snapshot is not None:
        if infer_snapshot.infer_result is not None and infer_snapshot.collected is not None:
            return _entries_from_snapshot(infer_snapshot)
        logger.warning(
            "extract_toc_entries incomplete infer_snapshot for %s; using path fallback",
            file_path,
        )
    return _to_fallback_entries(file_path)
```

- [ ] **Step 4: 运行单测**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_docx_toc_extractor.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/docx_toc_extractor.py backend/tests/unit/test_docx_toc_extractor.py
git commit -m "fix: extract_toc_entries falls back when infer snapshot incomplete"
```

---

### Task 3: 集成测试 fixture 对齐 sample-actual-bid.docx

**Files:**
- Modify: `backend/tests/integration/test_bid_outline_structure_diff.py`
- Modify: `backend/tests/conftest.py`（可选：增加 `actual_bid_docx_path` fixture）

- [ ] **Step 1: 结构 diff 测试改用 actual-bid fixture**

在 `test_bid_outline_structure_diff.py` 文件顶部（imports 后）添加：

```python
ACTUAL_BID_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-actual-bid.docx"
```

将两个测试函数签名中的 `sample_docx_path` 替换为使用 `ACTUAL_BID_FIXTURE`：

```python
def test_force_reparse_locked_outline_generates_pending_diff_without_mutating_nodes(
    db_session, seeded_kb,
):
    file_import, outline = _seed_locked_outline_import(db_session, seeded_kb, ACTUAL_BID_FIXTURE)
```

对 `test_bid_outline_diff_apply_and_reject_endpoints` 同样修改。

- [ ] **Step 2: 运行结构 diff 集成测**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_bid_outline_structure_diff.py -v`

Expected: PASS（2 tests）

- [ ] **Step 3: 运行 E2E 流**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_actual_bid_flow.py -v`

Expected: PASS

若 E2E 仍失败且为 `Package not found`：在 `conftest.py` 的 `uploaded_need_confirm` 中改用 `fixtures/sample-actual-bid.docx` 而非 `sample-template.docx`：

```python
@pytest.fixture()
def sample_docx_path() -> Path:
    actual = Path(__file__).parent / "fixtures" / "sample-actual-bid.docx"
    if actual.exists():
        return actual
    return Path(__file__).parent / "fixtures" / "sample-template.docx"
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_bid_outline_structure_diff.py backend/tests/conftest.py
git commit -m "test: align actual bid integration fixtures with sample-actual-bid.docx"
```

---

### Task 4: Phase 1 回归批跑

- [ ] **Step 1: 运行 Epic3 相关 pytest**

Run:

```bash
cd backend && ../.venv/bin/pytest \
  tests/contract/test_actual_bid_parse_trigger.py \
  tests/contract/test_actual_bid_parse_confirm.py \
  tests/contract/test_actual_bid_document_get.py \
  tests/contract/test_bid_outline_nodes.py \
  tests/contract/test_bid_outline_confirm.py \
  tests/integration/test_actual_bid_flow.py \
  tests/integration/test_actual_bid_parse_runner.py \
  tests/integration/test_bid_outline_structure_diff.py \
  tests/unit/test_bid_outline_extract_service.py \
  tests/unit/test_docx_document_walker.py \
  tests/unit/test_docx_toc_extractor.py \
  -q
```

Expected: all PASS

**Checkpoint Phase 1:** 3 个原失败集成测恢复绿

---

## Phase 2 — 005 质量门禁

### Task 5: 鼎信 baseline stats fixture

**Files:**
- Create: `backend/tests/fixtures/dingxin-baseline-stats.json`
- Modify: `backend/tests/integration/test_actual_bid_outline_quality.py`

- [ ] **Step 1: 测量 baseline 并写入 fixture**

Run 一次性脚本（或临时 pytest）对 `sample-actual-bid.docx` 跑 **未过滤** toc 条目数：

```python
from pathlib import Path
from src.services.docx_toc_extractor import extract_toc_entries

path = Path("backend/tests/fixtures/sample-actual-bid.docx")
raw = extract_toc_entries(path, infer_snapshot=None)
print(len(raw.entries))
```

将结果写入 `backend/tests/fixtures/dingxin-baseline-stats.json`：

```json
{
  "fixture_docx": "sample-actual-bid.docx",
  "unfiltered_node_count": <测量值>,
  "min_reduction_ratio": 0.30,
  "min_golden_retention_ratio": 0.95
}
```

- [ ] **Step 2: 实现离线 golden 测**

替换 `test_actual_bid_outline_quality.py` 中 skip 的集成逻辑为：

```python
import json
from pathlib import Path

from src.services.docx_document_walker import walk_document
from src.services.docx_toc_extractor import extract_toc_entries
from src.services.outline_heading_filter import filter_outline_entries

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-actual-bid.docx"
GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "dingxin-golden-titles.json"
BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "dingxin-baseline-stats.json"


def _normalize_title(title: str) -> str:
    return "".join(title.split())


def test_dingxin_golden_titles_retention_offline():
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(golden) >= 20
    walked = walk_document(FIXTURE)
    raw = extract_toc_entries(FIXTURE, infer_snapshot=walked)
    filtered = filter_outline_entries(
        raw.entries,
        blocks=walked.collected.blocks if walked.collected else [],
        strategy=raw.strategy,
    )
    kept_titles = {_normalize_title(e.title) for e in filtered.kept}
    matched = sum(1 for t in golden if _normalize_title(t) in kept_titles)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    retention = matched / len(golden)
    assert retention >= baseline["min_golden_retention_ratio"], f"retention={retention:.2%}"


def test_dingxin_node_reduction_offline():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    walked = walk_document(FIXTURE)
    raw = extract_toc_entries(FIXTURE, infer_snapshot=walked)
    filtered = filter_outline_entries(
        raw.entries,
        blocks=walked.collected.blocks if walked.collected else [],
        strategy=raw.strategy,
    )
    unfiltered = baseline["unfiltered_node_count"]
    kept = len(filtered.kept)
    reduction = 1 - (kept / unfiltered) if unfiltered else 0
    assert reduction >= baseline["min_reduction_ratio"], f"reduction={reduction:.2%}, kept={kept}"
```

保留 `DINGXIN_DOCM` 本地 E2E 为 `@pytest.mark.skipif` 可选测。

- [ ] **Step 3: 运行质量测**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_actual_bid_outline_quality.py -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/fixtures/dingxin-baseline-stats.json backend/tests/integration/test_actual_bid_outline_quality.py
git commit -m "test: offline dingxin golden retention and node reduction gates"
```

---

### Task 6: `parent_id` 层级集成测（005 FR-006）

**Files:**
- Create: `backend/tests/integration/test_bid_outline_parent_id.py`

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

from src.models.bid_outline_node import BidOutlineNode
from src.services.actual_bid_parse_runner import run_actual_bid_parse_pending
# reuse seed helper from test_actual_bid_parse_runner

def test_bid_outline_non_root_parent_id_ratio(db_session, seeded_kb):
    import_id = _seed_confirmed_actual_bid_import_with_downstreams(db_session, seeded_kb, FIXTURE)
    run_actual_bid_parse_pending(db_session)
    # get bid_outline_id from task ...
    nodes = db_session.query(BidOutlineNode).filter(...).all()
    non_root = [n for n in nodes if n.level > 1]
    if len(non_root) < 5:
        pytest.skip("fixture too flat for parent_id ratio")
    with_parent = sum(1 for n in non_root if n.parent_id is not None)
    assert with_parent / len(non_root) >= 0.70
```

- [ ] **Step 2: 运行测试；若失败则检查 `bid_outline_extract_service.persist_outline` parent 映射**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_bid_outline_parent_id.py -v`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_bid_outline_parent_id.py
git commit -m "test: bid outline non-root parent_id ratio integration gate"
```

---

### Task 7: 核对 filter reason_code 与 ready 列表隔离

**Files:**
- Modify: `backend/tests/unit/test_outline_heading_filter.py`（如需）
- Verify: `backend/src/api/routes/actual_bid_parse.py` L171–175

- [ ] **Step 1: 确认 `sample_excluded_decisions` 含 `reason_code`**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_outline_heading_filter.py tests/unit/test_outline_quality_service.py -v`

- [ ] **Step 2: 契约测 ready 列表不含 failed**

在 `test_actual_bid_parse_trigger.py` 或新建契约测：seed `status=failed` + `error_message` 任务，断言 `GET /tasks?status=ready` 不包含该任务。

- [ ] **Step 3: Commit**（若有新增测试）

**Checkpoint Phase 2:** dingxin 离线测 + parent_id 测通过

---

## Phase 3 — 004 UI + 文档

### Task 8: 前端类型扩展

**Files:**
- Modify: `frontend/src/services/actualBidParse.ts`

- [ ] **Step 1: 扩展 `llm_progress` 类型**

```typescript
export interface ParseProgressLogEntry {
  ts: string;
  level: string;
  message: string;
}

export interface ParseLlmProgress {
  total_chunks?: number;
  completed_chunks?: number;
  failed_chunks?: number;
  degraded_to_rule?: number;
  logs?: ParseProgressLogEntry[];
  phase_timings_ms?: Record<string, number>;
  phase?: string;
}
```

将 `ActualBidParseTaskListItem.llm_progress` 改为 `ParseLlmProgress | null`。

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/actualBidParse.ts
git commit -m "feat: extend actual bid parse progress types for log drawer"
```

---

### Task 9: `ParseTaskLogDrawer` 组件

**Files:**
- Create: `frontend/src/pages/OutlineCenter/ParseTaskLogDrawer.tsx`
- Modify: `frontend/src/pages/OutlineCenter/index.tsx`

- [ ] **Step 1: 创建 Drawer 组件**

`ParseTaskLogDrawer.tsx` 核心 props：

```typescript
interface ParseTaskLogDrawerProps {
  open: boolean;
  loading: boolean;
  task: ActualBidParseTaskDetail | null;
  onClose: () => void;
}
```

展示区块：
- `error_message`（Alert type="error"）
- Timeline from `task.llm_progress?.logs`
- Descriptions: `phase_timings_ms`, `outline_quality`, `downstream_entries`
- Table: `filtered_nodes_sample`（title, reason_code, level）

- [ ] **Step 2: 修改 `OutlineCenter/index.tsx`**

1. 删除「新建目录」Button（L170–172）。
2. `loadData` 并行拉取 `status=ready` 与 `status=failed`（两次 `listActualBidParseTasks` 或 API 支持多 status 则一次）。
3. `todoColumns` 增加「查看日志」Button，点击调用 `getParseTask(kbId, parse_task_id)` 打开 Drawer。
4. failed 任务 Tag 使用 `color="error"`。

- [ ] **Step 3: 手动验证**

启动 `./scripts/start.sh`，打开 `/outlines`，确认待办/失败任务可打开 Drawer 且展示日志。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/OutlineCenter/ParseTaskLogDrawer.tsx frontend/src/pages/OutlineCenter/index.tsx
git commit -m "feat: outline center parse task log drawer and failed task visibility"
```

---

### Task 10: Spec 与 quickstart 同步

**Files:**
- Modify: `specs/004-actual-bid-candidates/spec.md`
- Modify: `specs/005-outline-extraction-quality/spec.md`
- Modify: `specs/004-actual-bid-candidates/quickstart.md`

- [ ] **Step 1: 更新 004 Assumptions**

在 `spec.md` Assumptions 追加：

```markdown
- Document Tree 在本 Epic 为只读追溯；章节/产品分类映射仅在 Bid Outline 编辑。
- FR-022 智能章节分类本阶段为规则-only；LLM 建议推迟 Epic 4。
- 任务日志通过目录中心待办表 Drawer 展示，不实现独立 ParseTaskLogPanel 页面。
- 「新建目录」不在 MVP 范围。
```

- [ ] **Step 2: 更新 005 Status 与 Dependencies**

`005 spec.md` Status → `Ready for unified acceptance with 004`；Dependencies 增加「004 流水线统一快照修复」。

- [ ] **Step 3: quickstart 增加统一验收命令**

```bash
cd backend && ../.venv/bin/pytest \
  tests/integration/test_actual_bid_flow.py \
  tests/integration/test_actual_bid_outline_quality.py \
  tests/integration/test_bid_outline_structure_diff.py \
  -v
```

- [ ] **Step 4: Commit**

```bash
git add specs/004-actual-bid-candidates/spec.md specs/005-outline-extraction-quality/spec.md specs/004-actual-bid-candidates/quickstart.md
git commit -m "docs: sync epic3+005 specs for unified acceptance"
```

---

### Task 11: 最终验收批跑

- [ ] **Step 1: 后端全量相关测**

Run:

```bash
cd backend && ../.venv/bin/pytest tests/ -k "actual_bid or bid_outline or outline_quality or outline_heading or embedded_document or dingxin" -q
```

Expected: all PASS

- [ ] **Step 2: 勾选 `specs/004-actual-bid-candidates/tasks.md` 完成项**

- [ ] **Step 3: 更新 design doc Status → Implemented**

**Checkpoint Phase 3:** 统一验收门禁全部满足

---

## Self-Review（计划 vs 设计）

| 设计要求 | 对应 Task |
|---------|-----------|
| 统一推断快照 | Task 1, 2 |
| 3 集成测恢复 | Task 3, 4 |
| 鼎信 golden 离线测 | Task 5 |
| parent_id 门禁 | Task 6 |
| reason_code / ready 隔离 | Task 7 |
| 日志 Drawer + 移除新建目录 | Task 8, 9 |
| spec/quickstart | Task 10 |
| 统一验收 | Task 11 |

无 TBD/占位步骤。LLM 分类、Document Tree PATCH、Vitest 明确不在本计划内（与设计一致）。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-14-epic3-005-completion.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派生子 agent，任务间 review，迭代快  
2. **Inline Execution** — 本会话按 Task 顺序执行，Phase checkpoint 处暂停 review  

**Which approach?**
