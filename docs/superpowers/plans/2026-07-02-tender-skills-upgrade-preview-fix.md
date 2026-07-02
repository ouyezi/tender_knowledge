# tender_skills 升级 + 预览修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 `tender_skills` 至 `9717188`（anchor 对齐修复），确认 TK anchor 预览切片生效，刷新 CI fixture 与 quickstart，使 `tree/refine` 后章节预览仍含完整正文。

**Architecture:** 上游 `anchor_enricher` 写入正确的 `outline.json` anchor；TK 侧 `get_node_preview` 经 `outline_node_map` 反查后调用 `slice_section_by_anchor` 切片，与 DB level 解耦。历史数据不迁移，清库后重导即可。TK anchor 切片代码已在 `85314bc` 合入，本计划剩余工作主要是依赖对齐、fixture 刷新与回归验证。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pytest, React 18（无前端改动）, `doc-chunk` path dep `../../tender_skills`

**Design spec:** `docs/superpowers/specs/2026-07-02-tender-skills-upgrade-preview-fix-design.md`

---

## Baseline（执行前必读）

| 状态 | 内容 |
|------|------|
| ✅ 已合入 `85314bc` | `slice_section_by_anchor`、`resolve_outline_node_id`、`get_node_preview` anchor 路径 |
| ⬜ 待完成 | tender_skills 升级至 `9717188`、venv 重装、fixture 刷新、quickstart 更新 |
| ⚠️ 注意 | 当前 venv 可能指向旧版 `doc-chunk 0.1.0`（非 editable path），Task 1 必须重装 |
| ⚠️ 注意 | fixture 刷新后需保留 `tables/t0000.*` 侧车文件（样例 docx 无表格） |

## File Map

| 文件 | 职责 |
|------|------|
| `backend/pyproject.toml` | path 依赖声明（通常不改，仅重装） |
| `backend/src/services/doc_chunk/section_slice.py` | `slice_section_by_anchor`（已实现，Task 5 验证） |
| `backend/src/services/doc_chunk/outline_store.py` | `resolve_outline_node_id`（已实现，Task 5 验证） |
| `backend/src/services/knowledge/entry_content_service.py` | `get_node_preview` anchor 路径（已实现，Task 5 验证） |
| `backend/tests/fixtures/doc_chunk_workspace_minimal/` | CI fixture，Task 2 刷新 |
| `backend/tests/unit/test_doc_chunk_fixture_anchors.py` | 新增：fixture anchor 切片 smoke 测试 |
| `specs/009-doc-chunk-integration/quickstart.md` | 更新已验证 commit SHA |

---

### Task 1: 升级 tender_skills 并重装 backend 依赖

**Files:**
- Verify: `../tender_skills`（同级仓库）
- Verify: `backend/pyproject.toml`

- [ ] **Step 1: 确认 tender_skills 在目标 commit**

Run:
```bash
cd /Users/tongqianni/xlab/tender_skills
git fetch origin
git checkout 97171885e267afbc85a2c02760e16d95d64a9d2d
git rev-parse HEAD
```
Expected: `97171885e267afbc85a2c02760e16d95d64a9d2d`

- [ ] **Step 2: tender_skills 自检**

Run:
```bash
cd /Users/tongqianni/xlab/tender_skills
pip install -e ".[dev]"
python -m pytest tests/unit tests/contract -q
```
Expected: 全部 PASS

- [ ] **Step 3: 在 tender_knowledge venv 重装 doc-chunk**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pip install -e ".[dev]" -e "../../tender_skills[dev]"
../.venv/bin/python -c "import importlib.metadata as m; print(m.version('doc-chunk'))"
../.venv/bin/python -c "import doc_chunk; print(doc_chunk.__file__)"
```
Expected:
- version 输出 `0.2.0`
- `__file__` 路径含 `tender_skills/src/doc_chunk`

- [ ] **Step 4: Commit（若 quickstart 尚未更新则跳过，Task 4 一并提交）**

本 Task 无代码改动，无需单独 commit。

---

### Task 2: 刷新 doc_chunk_workspace_minimal fixture

**Files:**
- Modify: `backend/tests/fixtures/doc_chunk_workspace_minimal/`（整目录替换，保留 tables 侧车）
- Read: `specs/009-doc-chunk-integration/quickstart.md`（fixture 刷新命令）

- [ ] **Step 1: 备份 tables 侧车**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
TABLES_BACKUP="/tmp/tk-fixture-tables-$$"
mkdir -p "$TABLES_BACKUP"
cp -R tests/fixtures/doc_chunk_workspace_minimal/tables "$TABLES_BACKUP/"
ls "$TABLES_BACKUP/tables"
```
Expected: 含 `index.json`、`manifest.json`、`t0000.json`（及 `t0000.docx` 若存在）

- [ ] **Step 2: 用新 tender_skills pipeline 生成 workspace**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
OUT="/tmp/tk-ws-minimal-$$"
rm -rf "$OUT"
../.venv/bin/python -c "
from pathlib import Path
from doc_chunk.api import run_pipeline
run_pipeline(
    Path('tests/fixtures/sample-actual-bid.docx'),
    Path('$OUT'),
    overwrite=True,
    skip_refine=True,
    skip_enrich=True,
    promote_headings='auto',
)
print('outline nodes:', len(__import__('json').loads((Path('$OUT')/'outline.json').read_text())['nodes']))
"
```
Expected: 打印 `outline nodes: 2`（或 ≥1），无 exception

- [ ] **Step 3: 替换 fixture 并恢复 tables 侧车**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
rm -rf tests/fixtures/doc_chunk_workspace_minimal
mkdir -p tests/fixtures/doc_chunk_workspace_minimal
cp -R "$OUT"/* tests/fixtures/doc_chunk_workspace_minimal/
cp -R "$TABLES_BACKUP/tables" tests/fixtures/doc_chunk_workspace_minimal/
```
Expected: `tests/fixtures/doc_chunk_workspace_minimal/outline.json` 存在且 nodes 含 `anchor.char_start`

- [ ] **Step 4: 验证 fixture import 测试通过**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/unit/test_doc_chunk_import_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/tongqianni/xlab/tender_knowledge
git add backend/tests/fixtures/doc_chunk_workspace_minimal/
git commit -m "$(cat <<'EOF'
test: refresh doc_chunk_workspace_minimal for tender_skills 9717188

EOF
)"
```

---

### Task 3: Fixture anchor 切片 smoke 测试

**Files:**
- Create: `backend/tests/unit/test_doc_chunk_fixture_anchors.py`
- Read: `backend/tests/fixtures/doc_chunk_workspace_minimal/outline.json`
- Read: `backend/tests/fixtures/doc_chunk_workspace_minimal/content.md`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_doc_chunk_fixture_anchors.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from src.services.doc_chunk.section_slice import slice_section_by_anchor

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def _load_fixture_outline() -> dict:
    return json.loads((FIXTURE_ROOT / "outline.json").read_text(encoding="utf-8"))


def test_fixture_outline_nodes_have_anchor_char_start():
    outline = _load_fixture_outline()
    nodes = outline.get("nodes") or []
    assert nodes, "fixture outline must have nodes"
    for node in nodes:
        anchor = node.get("anchor") or {}
        assert anchor.get("char_start") is not None, f"{node['node_id']} missing char_start"


def test_fixture_slice_child_section_has_body():
    content_md = (FIXTURE_ROOT / "content.md").read_text(encoding="utf-8")
    outline = _load_fixture_outline()
    child_id = outline["nodes"][1]["node_id"]
    section_md = slice_section_by_anchor(content_md, outline, child_id)
    assert section_md is not None
    assert "二级章节正文" in section_md
    assert "这是正文段落" not in section_md
```

- [ ] **Step 2: Run test to verify it passes**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/unit/test_doc_chunk_fixture_anchors.py -v
```
Expected: PASS（Task 2 刷新 fixture 后）

- [ ] **Step 3: Commit**

```bash
cd /Users/tongqianni/xlab/tender_knowledge
git add backend/tests/unit/test_doc_chunk_fixture_anchors.py
git commit -m "$(cat <<'EOF'
test: assert doc_chunk fixture anchors slice section body

EOF
)"
```

---

### Task 4: 更新 quickstart 已验证 commit

**Files:**
- Modify: `specs/009-doc-chunk-integration/quickstart.md:7`

- [ ] **Step 1: 更新 commit SHA**

将 `specs/009-doc-chunk-integration/quickstart.md` 第 7 行：

```markdown
1. `tender_skills` 已安装且通过测试（已验证 commit: `3eb2a0d916e250210d79c32e07e7f4d0f888611a`）：
```

改为：

```markdown
1. `tender_skills` 已安装且通过测试（已验证 commit: `97171885e267afbc85a2c02760e16d95d64a9d2d`）：
```

- [ ] **Step 2: Commit**

```bash
cd /Users/tongqianni/xlab/tender_knowledge
git add specs/009-doc-chunk-integration/quickstart.md
git commit -m "$(cat <<'EOF'
docs: record tender_skills 9717188 as verified doc-chunk commit

EOF
)"
```

---

### Task 5: 验证 TK anchor 预览实现（已合入，回归确认）

**Files:**
- Verify: `backend/src/services/doc_chunk/section_slice.py`
- Verify: `backend/src/services/doc_chunk/outline_store.py`
- Verify: `backend/src/services/knowledge/entry_content_service.py`
- Test: `backend/tests/unit/test_doc_chunk_section_slice.py`
- Test: `backend/tests/unit/test_outline_store.py`
- Test: `backend/tests/unit/test_knowledge_entry_content.py`

- [ ] **Step 1: 确认 preview 走 anchor 路径**

打开 `backend/src/services/knowledge/entry_content_service.py`，确认 `get_node_preview` 含：

```python
outline_payload = load_outline(document_id=doc_id)
# ...
outline_node_id = resolve_outline_node_id(document_id=doc_id, tree_node_id=node_uuid)
section_md = slice_section_by_anchor(content_md, outline_payload, outline_node_id)
```

- [ ] **Step 2: 运行 anchor 切片单测**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest \
  tests/unit/test_doc_chunk_section_slice.py \
  tests/unit/test_outline_store.py \
  tests/unit/test_knowledge_entry_content.py::test_get_node_preview_uses_anchor_not_db_level \
  tests/unit/test_knowledge_entry_content.py::test_get_node_preview_parent_includes_child_content \
  tests/unit/test_knowledge_entry_content.py::test_get_node_preview_returns_preface_content \
  -v
```
Expected: 全部 PASS

- [ ] **Step 3: 运行 enrich 相关单测**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest \
  tests/unit/test_doc_chunk_section_slice.py::test_slice_section_from_payload_uses_anchor_char_start \
  tests/unit/test_knowledge_asset_seed.py \
  tests/unit/test_doc_chunk_enrich_document_tree.py \
  -v
```
Expected: 全部 PASS

---

### Task 6: 全量 doc_chunk + knowledge 回归

**Files:** (none — verification only)

- [ ] **Step 1: doc_chunk 单元测试**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/unit/test_doc_chunk_*.py -q
```
Expected: 全部 PASS

- [ ] **Step 2: knowledge 单元测试**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/unit/test_knowledge_*.py tests/unit/test_entry_tree_*.py -q
```
Expected: 全部 PASS

- [ ] **Step 3: integration preview 测试（若环境 fixture 正常）**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
../.venv/bin/pytest tests/integration/test_knowledge_flow.py -k preview -v
```
Expected: PASS

> 若 `test_knowledge_api.py` 因 taxonomy fixture 的 `kb_id` 问题 ERROR，属既有测试环境问题，不影响本 feature 验收；以 Task 5 服务层单测 + Task 7 手工验收为准。

---

### Task 7: 手工验收（清库重导）

**Files:** (none — manual checklist)

- [ ] **Step 1: 清空旧文档数据**

删除 storage 下旧 `documents/` 目录，或删除 KB 内全部已导入文档（用户已确认可删历史数据）。

- [ ] **Step 2: 启动服务并导入标书**

```bash
cd /Users/tongqianni/xlab/tender_knowledge
.venv/bin/python startup.py
```

在 UI 或通过 API 重新导入一份含 TOC 的标书（如餐补类 235 节点文档）。

- [ ] **Step 3: 验证预览含正文**

1. 进入知识录入页，选择刚导入的文档
2. 点击 `2.1合同条款偏离表` 或类似节点
3. 确认预览区 `content_md` 含完整表格/段落，而非仅一行封面/目录

- [ ] **Step 4: 验证 refine 后预览不退化**

1. 点击「刷新」执行 `tree/refine`
2. 再次点击同一节点
3. 确认预览仍含完整正文（与 refine 前一致或更完整）

- [ ] **Step 5: 验证父节点含子孙正文**

点击一级章节节点，确认预览包含其全部子节正文。

---

## Spec Coverage Checklist

| Spec 要求 | 对应 Task |
|-----------|-----------|
| G1 升级 tender_skills 9717188 | Task 1 |
| G2 preview/enrich anchor 切片 | Task 5（已实现） |
| G3 refine 后预览完整 | Task 5 + Task 7 |
| G4 刷新 fixture + quickstart | Task 2 + Task 4 |
| G5 历史不迁移，清库重导 | Task 7 |
| anchor 切片单测 | Task 5 |
| fixture anchor smoke | Task 3 |
| enrich 回归 | Task 5 Step 3 + Task 6 |
| 错误处理（outline 缺失等） | Task 5（`85314bc` 已实现） |

---

## 执行选项

Plan complete and saved to `docs/superpowers/plans/2026-07-02-tender-skills-upgrade-preview-fix.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派一个全新 subagent，Task 间做 review，迭代快
2. **Inline Execution** — 在本 session 用 executing-plans 批量执行，checkpoint 处暂停 review

**Which approach?**
