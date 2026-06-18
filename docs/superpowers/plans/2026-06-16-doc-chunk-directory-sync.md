# doc_chunk 目录提取依赖同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `tender_knowledge` doc_chunk 默认解析路径对齐到最新 `tender_skills`（含编号修复与 003 契约），刷新 CI fixture 并新增本地餐补大样例 import 回归测试。

**Architecture:** 保持 `run_doc_chunk_pipeline` → `import_workspace` 薄适配层不变；通过 editable path 依赖升级 + 重导 `doc_chunk_workspace_minimal` 同步工作区 JSON；适配层仅在 pytest 失败时最小修复；大样例用 skip 式集成测试覆盖 pipeline + 落库不变量。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest, `doc-chunk`（path: `../../tender_skills`）

**Design doc:** `docs/superpowers/specs/2026-06-16-doc-chunk-directory-sync-design.md`  
**Related spec:** `specs/009-doc-chunk-integration/quickstart.md`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/pyproject.toml` | path 依赖 `doc-chunk @ file:../../tender_skills`（通常不改，仅重装） |
| `backend/tests/fixtures/doc_chunk_workspace_minimal/*` | CI 注入用 workspace JSON（全量重导） |
| `backend/tests/fixtures/sample-actual-bid.docx` | minimal fixture 生成源 docx |
| `backend/src/services/doc_chunk/linkage_validation.py` | 标题匹配（仅测试失败时改） |
| `backend/tests/integration/test_doc_chunk_parse_flow.py` | CI 端到端（mock pipeline，断言 candidate_count） |
| `backend/tests/integration/test_doc_chunk_canbu_import.py` | **新建** 本地大样例 pipeline + import |
| `backend/tests/unit/test_doc_chunk_linkage_validation.py` | 标题匹配单测 |
| `specs/009-doc-chunk-integration/quickstart.md` | 已验证 commit + 场景 6 命令 |

**Run tests from:** `backend/` with `../.venv/bin/pytest`（或项目根 `.venv/bin/python -m pytest`）

**tender_skills 目标 commit:** `163db06`（联调时 `cd ../tender_skills && git rev-parse --short HEAD` 记入 quickstart）

---

### Task 1: 验证并升级 tender_skills 依赖

**Files:**
- Verify: `../tender_skills`（同级仓库）
- Verify: `backend/pyproject.toml`

- [ ] **Step 1: tender_skills 自检**

```bash
cd /Users/tongqianni/xlab/tender_skills
git fetch origin
git checkout 163db06   # 或 git checkout main && git pull
pip install -e ".[dev]"
python -m pytest tests/unit tests/contract -q
```

Expected: 全部 PASS（contract 53+ 项）

- [ ] **Step 2: 重装 tk backend 依赖**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
pip install -e ".[dev]"
python -c "import doc_chunk; from doc_chunk.extract.docx_numbering import merge_list_prefix; print('doc_chunk OK', merge_list_prefix('资格证明', '六、'))"
```

Expected: 输出 `doc_chunk OK 六、资格证明`（证明 `163db06` numbering 模块可用）

- [ ] **Step 3: 记录实际 commit 到工作笔记**

```bash
cd /Users/tongqianni/xlab/tender_skills && git rev-parse HEAD
```

将完整 SHA 留给 Task 5 quickstart 更新使用。

- [ ] **Step 4: Commit（若无 pyproject 变更可跳过）**

仅当 `pyproject.toml` 有改动时：

```bash
git add backend/pyproject.toml
git commit -m "chore: align doc-chunk path dependency with tender_skills 163db06"
```

---

### Task 2: 重导 `doc_chunk_workspace_minimal` fixture

**Files:**
- Replace: `backend/tests/fixtures/doc_chunk_workspace_minimal/`（8 个 JSON 文件）
- Source: `backend/tests/fixtures/sample-actual-bid.docx`

- [ ] **Step 1: 用最新 pipeline 生成工作区**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
FIXTURE_SRC="tests/fixtures/sample-actual-bid.docx"
OUT="/tmp/tk-ws-minimal-$$"
python -m doc_chunk.cli.main run "$FIXTURE_SRC" "$OUT" \
  --overwrite --skip-refine --skip-enrich
ls -la "$OUT"
```

Expected: 存在 `manifest.json`、`outline.json`、`document_tree.json`、`linkage.json`、`chunks/index.json`

- [ ] **Step 2: 备份并替换 fixture 目录**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
FIXTURE_DIR="tests/fixtures/doc_chunk_workspace_minimal"
cp -R "$FIXTURE_DIR" "${FIXTURE_DIR}.bak"
rm -rf "$FIXTURE_DIR"
mkdir -p "$FIXTURE_DIR"
cp -R "$OUT"/* "$FIXTURE_DIR"/
# 确认 chunk 子目录与 images 一并拷贝
find "$FIXTURE_DIR" -type f | sort
```

Expected: 至少 8 个文件，与 design §4.2 列表一致

- [ ] **Step 3: 记录新 fixture 关键指标（供 Task 3 更新断言）**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
python - <<'PY'
import json
from pathlib import Path
root = Path("tests/fixtures/doc_chunk_workspace_minimal")
outline = json.loads((root / "outline.json").read_text())["nodes"]
linkage = json.loads((root / "linkage.json").read_text())["entries"]
chunks = json.loads((root / "chunks/index.json").read_text())["chunks"]
preface = [c for c in chunks if c.get("title") == "Preface"]
main = [c for c in chunks if c.get("heading_level") is not None]
print("outline_count", len(outline))
print("linkage_count", len(linkage))
print("chunk_count", len(chunks))
print("main_chunk_count", len(main))
print("candidate_expect", len([e for e in linkage if e.get("chunk_ids") and e.get("primary_chunk_id")]))
PY
```

记下 `candidate_expect` 数值，用于更新 `test_doc_chunk_parse_flow` 的 `assert candidate_count == N`。

- [ ] **Step 4: Commit fixture**

```bash
git add backend/tests/fixtures/doc_chunk_workspace_minimal/
git commit -m "test: refresh doc_chunk_workspace_minimal from tender_skills pipeline"
```

---

### Task 3: CI 测试全绿（含条件性适配修复）

**Files:**
- Modify (if needed): `backend/tests/integration/test_doc_chunk_parse_flow.py`
- Modify (if needed): `backend/src/services/doc_chunk/linkage_validation.py`
- Modify (if needed): `backend/tests/unit/test_doc_chunk_*.py`

- [ ] **Step 1: 跑 doc_chunk 单测与集成测**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
pytest tests/unit/test_doc_chunk_*.py tests/integration/test_doc_chunk_parse_flow.py -v
```

- [ ] **Step 2: 若 `test_doc_chunk_parse_flow` 的 candidate_count 失败，更新期望值**

在 `backend/tests/integration/test_doc_chunk_parse_flow.py` 末尾断言处：

```python
    # candidate_count 来自 fixture linkage 中非空 chunk 且非 Preface 的条目数
    # 刷新 fixture 后见 Task 2 Step 3 打印的 candidate_expect
    assert candidate_count == <candidate_expect>  # 替换为实际值，例如 2
```

- [ ] **Step 3: 若 enrich/candidates 因编号标题被跳过，增强 `normalize_title`**

仅当 `test_doc_chunk_enrich_document_tree` 或 `test_doc_chunk_candidates_mapper` 失败且日志含 `*_outline_mismatch` 时执行。

Modify `backend/src/services/doc_chunk/linkage_validation.py`:

```python
import re

_NUM_PREFIX_RE = re.compile(
    r"^[一二三四五六七八九十百零]+[、.．]|^\d+(?:\.\d+)*[、.．\s]+"
)


def normalize_title(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = _NUM_PREFIX_RE.sub("", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[（）()【】\[\]《》<>「」\"'""''\"'':：,，.。;；!！?？\-—_·•]", "", text)
    return text
```

在 `backend/tests/unit/test_doc_chunk_linkage_validation.py` 追加：

```python
def test_titles_compatible_strips_chinese_list_prefix():
    assert titles_compatible("六、资格证明文件", "资格证明文件")
```

Run: `pytest tests/unit/test_doc_chunk_linkage_validation.py -v`  
Expected: PASS

- [ ] **Step 4: 跑 actual_bid 契约回归**

```bash
pytest tests/contract/test_actual_bid_parse*.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: Commit 修复（若有）**

```bash
git add backend/tests/integration/test_doc_chunk_parse_flow.py \
        backend/src/services/doc_chunk/linkage_validation.py \
        backend/tests/unit/test_doc_chunk_linkage_validation.py
git commit -m "fix: align doc_chunk import with refreshed tender_skills workspace output"
```

---

### Task 4: 本地餐补大样例 import 集成测试

**Files:**
- Create: `backend/tests/integration/test_doc_chunk_canbu_import.py`

- [ ] **Step 1: 写入集成测试（skip 无环境变量）**

```python
# backend/tests/integration/test_doc_chunk_canbu_import.py
"""Local-only regression: real doc_chunk pipeline + import_workspace on large bid."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.bid_outline_node import BidOutlineNode
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.doc_chunk.import_service import import_workspace
from src.services.doc_chunk.pipeline_runner import run_doc_chunk_pipeline

CANBU = os.environ.get("DOC_CHUNK_CANBU_FIXTURE")
DINGXIN = os.environ.get("DOC_CHUNK_DINGXIN_FIXTURE")

FIXTURES = [p for p in (CANBU, DINGXIN) if p]
pytestmark = pytest.mark.skipif(not FIXTURES, reason="set DOC_CHUNK_CANBU_FIXTURE and/or DOC_CHUNK_DINGXIN_FIXTURE")


@pytest.mark.parametrize("fixture_path", FIXTURES)
def test_large_bid_pipeline_import_invariants(db_session, seeded_kb, tmp_path, fixture_path: str):
    src = Path(fixture_path)
    assert src.is_file(), f"missing fixture: {src}"

    import_id = uuid4()
    parse_task_id = uuid4()
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name=src.name,
        file_type=FileType.docx,
        file_size=src.stat().st_size,
        storage_path=f"{seeded_kb.kb_id}/{src.name}",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    task = ActualBidParseTask(
        parse_task_id=parse_task_id,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
    )
    db_session.add(file_import)
    db_session.add(task)
    db_session.commit()

    workspace = tmp_path / "ws"
    workspace.mkdir()
    run_doc_chunk_pipeline(src, workspace)

    result = import_workspace(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        document_id=None,
        parse_task_id=parse_task_id,
        workspace=workspace,
        file_import=file_import,
        task=task,
    )
    db_session.commit()

    document = db_session.get(Document, result.document_id)
    assert document is not None
    assert document.parse_status == DocumentParseStatus.ready

    outline_count = (
        db_session.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == result.bid_outline_id)
        .count()
    )
    candidate_count = (
        db_session.query(CandidateKnowledge)
        .filter(CandidateKnowledge.source_doc_id == result.document_id)
        .count()
    )
    tree_nodes = (
        db_session.query(DocumentTreeNode)
        .filter(DocumentTreeNode.document_id == result.document_id)
        .all()
    )
    tree_ids = [str(n.node_id) for n in tree_nodes]
    assert len(tree_ids) == len(set(tree_ids)), "document_tree node_id must be globally unique"

    assert outline_count > 0
    ratio = candidate_count / max(outline_count, 1)
    assert 0.8 <= ratio <= 1.2, f"candidate/outline ratio out of range: {ratio:.2f}"

    print(
        f"[{src.name}] outline={outline_count} candidates={candidate_count} "
        f"tree={len(tree_nodes)} ratio={ratio:.2f}"
    )
```

- [ ] **Step 2: 确认 CI 下 skip**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
pytest tests/integration/test_doc_chunk_canbu_import.py -v
```

Expected: `SKIPPED`（无环境变量）

- [ ] **Step 3: 本地跑餐补样例（开发者机器）**

```bash
export DOC_CHUNK_CANBU_FIXTURE="/path/to/餐补标书.docx"
pytest tests/integration/test_doc_chunk_canbu_import.py -v -s
```

Expected: PASS，stdout 打印 `outline=... candidates=... ratio=...`

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_doc_chunk_canbu_import.py
git commit -m "test: add local canbu/dingxin doc_chunk import regression"
```

---

### Task 5: 更新 quickstart 文档

**Files:**
- Modify: `specs/009-doc-chunk-integration/quickstart.md`

- [ ] **Step 1: 在「前置条件」第 1 条后追加已验证 commit**

```markdown
1. `tender_skills` 已安装且 003 + 编号修复通过（已验证 commit: `<FULL_SHA>`）：
```

将 `<FULL_SHA>` 替换为 Task 1 Step 3 记录的值。

- [ ] **Step 2: 修正场景 6 文件名与命令**

将：

```bash
pytest tests/integration/test_doc_chunk_canbu_parse.py -v
```

改为：

```bash
export DOC_CHUNK_CANBU_FIXTURE="/path/to/餐补标书.docx"
# 可选第二份样例
export DOC_CHUNK_DINGXIN_FIXTURE="/path/to/鼎信标书.docx"
cd backend && pytest tests/integration/test_doc_chunk_canbu_import.py -v -s
```

**验证指标**（与测试一致）：

- `document_tree` 节点 ID 唯一
- `candidate_count / outline_count ∈ [0.8, 1.2]`
- `document.parse_status == ready`

- [ ] **Step 3: 在「场景 5」补充 fixture 刷新命令**

```bash
python -m doc_chunk.cli.main run tests/fixtures/sample-actual-bid.docx /tmp/ws-minimal \
  --overwrite --skip-refine --skip-enrich
# 拷贝 /tmp/ws-minimal → tests/fixtures/doc_chunk_workspace_minimal/
```

- [ ] **Step 4: Commit**

```bash
git add specs/009-doc-chunk-integration/quickstart.md
git commit -m "docs: update doc_chunk quickstart for tender_skills sync and canbu regression"
```

---

### Task 6: 最终验收清单

- [ ] **Step 1: CI 门禁全绿**

```bash
cd /Users/tongqianni/xlab/tender_knowledge/backend
pytest tests/unit/test_doc_chunk_*.py \
       tests/integration/test_doc_chunk_parse_flow.py \
       tests/contract/test_actual_bid_parse*.py -q
```

Expected: 0 failed

- [ ] **Step 2: 本地餐补回归（有样例时）**

```bash
export DOC_CHUNK_CANBU_FIXTURE="/path/to/餐补标书.docx"
pytest tests/integration/test_doc_chunk_canbu_import.py -v -s
```

- [ ] **Step 3: 可选人工抽检**

对餐补样例解析结果在确认向导检查：

- 目录标题含「六、」等编号前缀
- 候选详情正文非空

- [ ] **Step 4: 更新 design spec status（可选）**

在 `docs/superpowers/specs/2026-06-16-doc-chunk-directory-sync-design.md` 将 `Status` 改为 `Implemented`。

---

## Spec Coverage Checklist

| Design § | Task |
|----------|------|
| §1.2 依赖对齐 | Task 1 |
| §1.2 CI 全绿 | Task 2, 3 |
| §1.2 本地大样例 | Task 4 |
| §1.2 最小适配 | Task 3 Step 3（条件） |
| §4.2 fixture 刷新 | Task 2 |
| §5.1 CI 门禁 | Task 3, 6 |
| §5.2 canbu import 测试 | Task 4 |
| §7 quickstart | Task 5 |
| §6 回滚 | 文档已覆盖，无代码任务 |

## Self-Review

- 无 TBD / 占位步骤
- 类型与 import 路径与现有 `import_workspace` / `ActualBidParseTask` 一致
- `test_doc_chunk_canbu_import.py` 使用真实 pipeline，CI 默认 skip
- fixture 候选条数用 Task 2 脚本输出，避免硬编码过时值
