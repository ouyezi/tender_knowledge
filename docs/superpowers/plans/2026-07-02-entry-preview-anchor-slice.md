# Entry Preview Anchor Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 知识录入预览与 outline payload 切片全链路改用 `outline.json` 的 `anchor.char_start` 定位，不再用标题关键词搜索定边界。

**Architecture:** 在 `section_slice.py` 新增纯 anchor 切片函数；`slice_section_markdown_from_payload` 委托给它；`get_node_preview` 通过 `outline_node_map` 反查 outline 节点后走 anchor 路径。旧标题匹配函数保留但 preview/enrich 不再调用。

**Tech Stack:** Python 3.11, FastAPI, pytest, SQLAlchemy.

**Design spec:** `docs/superpowers/specs/2026-07-02-entry-preview-anchor-slice-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/services/doc_chunk/section_slice.py` | 新增 `slice_section_by_anchor`、`_section_end_by_anchor`；`from_payload` 改委托 |
| `backend/src/services/doc_chunk/outline_store.py` | 新增 `resolve_outline_node_id` 反查工具 |
| `backend/src/services/knowledge/entry_content_service.py` | `get_node_preview` 读 outline + map，走 anchor 切片 |
| `backend/tests/unit/test_doc_chunk_section_slice.py` | anchor 切片单测 + 更新旧契约测试 |
| `backend/tests/unit/test_knowledge_entry_content.py` | preview 测试补 outline/map fixture |

---

## Task 1: `slice_section_by_anchor` 核心切片

**Files:**
- Modify: `backend/src/services/doc_chunk/section_slice.py`
- Test: `backend/tests/unit/test_doc_chunk_section_slice.py`

- [ ] **Step 1: Write failing tests**

在 `backend/tests/unit/test_doc_chunk_section_slice.py` 末尾追加：

```python
from src.services.doc_chunk.section_slice import slice_section_by_anchor


def _outline_with_anchors(content_md: str) -> dict:
  parent_start = content_md.index("# 第一章")
  child_start = content_md.index("## 1.1")
  sibling_start = content_md.index("## 1.2")
  return {
    "nodes": [
      {
        "node_id": "n1",
        "title": "第一章 总则",
        "level": 1,
        "parent_id": None,
        "sort_order": 0,
        "anchor": {"char_start": parent_start, "char_end": parent_start + 10},
      },
      {
        "node_id": "n2",
        "title": "1.1 范围",
        "level": 2,
        "parent_id": "n1",
        "sort_order": 1,
        "anchor": {"char_start": child_start, "char_end": child_start + 10},
      },
      {
        "node_id": "n3",
        "title": "1.2 其他",
        "level": 2,
        "parent_id": "n1",
        "sort_order": 2,
        "anchor": {"char_start": sibling_start, "char_end": sibling_start + 10},
      },
    ]
  }


def test_slice_section_by_anchor_child_section():
  content_md = "# 第一章 总则\n\n父内容\n\n## 1.1 范围\n\n子内容\n\n## 1.2 其他\n\n忽略\n"
  outline = _outline_with_anchors(content_md)
  md = slice_section_by_anchor(content_md, outline, "n2")
  assert md is not None
  assert "子内容" in md
  assert "父内容" not in md
  assert "忽略" not in md


def test_slice_section_by_anchor_parent_includes_children():
  content_md = "# 第一章 总则\n\n父内容\n\n## 1.1 范围\n\n子内容\n\n## 1.2 其他\n\n忽略\n"
  outline = _outline_with_anchors(content_md)
  md = slice_section_by_anchor(content_md, outline, "n1")
  assert md is not None
  assert "父内容" in md
  assert "子内容" in md
  assert "忽略" not in md


def test_slice_section_by_anchor_ignores_db_level_mismatch():
  content_md = "# 第一章 总则\n\n父内容\n\n## 1.1 范围\n\n子内容\n\n## 1.2 其他\n\n忽略\n"
  outline = _outline_with_anchors(content_md)
  # 故意把 n1 level 改成 3，anchor 切片不应受影响
  outline["nodes"][0]["level"] = 3
  md = slice_section_by_anchor(content_md, outline, "n1")
  assert md is not None
  assert "子内容" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/unit/test_doc_chunk_section_slice.py::test_slice_section_by_anchor_child_section -v`  
Expected: FAIL `ImportError` or `AttributeError: slice_section_by_anchor`

- [ ] **Step 3: Implement `slice_section_by_anchor`**

在 `backend/src/services/doc_chunk/section_slice.py` 追加（放在 `slice_section_markdown_from_payload` 之前）：

```python
def _is_descendant_of(
    node_id: str,
    ancestor_id: str,
    node_map: dict[str, OutlineSliceNode],
) -> bool:
    cursor = node_map.get(node_id)
    seen: set[str] = set()
    while cursor is not None and cursor.parent_id:
        if cursor.parent_id in seen:
            break
        if cursor.parent_id == ancestor_id:
            return True
        seen.add(cursor.parent_id)
        cursor = node_map.get(cursor.parent_id)
    return False


def _ordered_anchor_nodes(nodes: list[OutlineSliceNode]) -> list[OutlineSliceNode]:
    return sorted(
        nodes,
        key=lambda item: (
            item.anchor_char_start if item.anchor_char_start is not None else 10**9,
            item.sort_order,
            item.node_id,
        ),
    )


def _section_end_by_anchor(
    *,
    start: int,
    node_id: str,
    nodes: list[OutlineSliceNode],
    node_map: dict[str, OutlineSliceNode],
    content_len: int,
) -> int:
    for other in _ordered_anchor_nodes(nodes):
        other_start = other.anchor_char_start
        if other_start is None or other_start <= start:
            continue
        if _is_descendant_of(other.node_id, node_id, node_map):
            continue
        return other_start
    return content_len


def _preface_end_by_anchor(nodes: list[OutlineSliceNode]) -> int:
    starts = [node.anchor_char_start for node in nodes if node.anchor_char_start is not None]
    return min(starts) if starts else 0


def slice_section_by_anchor(
    content_md: str,
    outline_payload: dict[str, Any],
    outline_node_id: str,
) -> str | None:
    if not content_md.strip():
        return None
    nodes = outline_nodes_from_payload(outline_payload)
    if not nodes:
        return None
    node_map = {node.node_id: node for node in nodes}

    if outline_node_id == PREFACE_NODE_ID:
        end = _preface_end_by_anchor(nodes)
        return content_md[:end]

    node = node_map.get(outline_node_id)
    if node is None:
        return None
    start = node.anchor_char_start
    if start is None:
        return None
    end = _section_end_by_anchor(
        start=start,
        node_id=outline_node_id,
        nodes=nodes,
        node_map=node_map,
        content_len=len(content_md),
    )
    return content_md[start:end]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest tests/unit/test_doc_chunk_section_slice.py::test_slice_section_by_anchor_child_section tests/unit/test_doc_chunk_section_slice.py::test_slice_section_by_anchor_parent_includes_children tests/unit/test_doc_chunk_section_slice.py::test_slice_section_by_anchor_ignores_db_level_mismatch -v`  
Expected: PASS (3 tests)

---

## Task 2: `from_payload` 委托 + 契约变更测试

**Files:**
- Modify: `backend/src/services/doc_chunk/section_slice.py`
- Modify: `backend/tests/unit/test_doc_chunk_section_slice.py`

- [ ] **Step 1: Update `slice_section_markdown_from_payload`**

将 `section_slice.py` 中现有函数改为：

```python
def slice_section_markdown_from_payload(
    content_md: str,
    outline_payload: dict[str, Any],
    outline_node_id: str,
) -> str | None:
    return slice_section_by_anchor(content_md, outline_payload, outline_node_id)
```

- [ ] **Step 2: Update `test_slice_section_ignores_wrong_anchor_char_start`**

将断言改为 anchor 契约（信 anchor，不信标题）：

```python
def test_slice_section_from_payload_uses_anchor_char_start():
    content_md = (
        "承诺人：某公司\n\n"
        "### （四）不违法分包转包承诺书\n\n"
        "错误段落\n\n"
        "##### (6)九阳\n\n"
        "![docx-img-457](images/docx-img-457.png)\n\n"
        "##### (7)美的\n\n"
        "下一节\n"
    )
    n71_start = content_md.index("##### (6)九阳")
    n72_start = content_md.index("##### (7)美的")
    outline_payload = {
        "nodes": [
            {
                "node_id": "n71",
                "title": "(6)九阳",
                "level": 5,
                "parent_id": "n70",
                "sort_order": 71,
                "anchor": {"char_start": n71_start, "char_end": n71_start + 20},
            },
            {
                "node_id": "n72",
                "title": "(7)美的",
                "level": 5,
                "parent_id": "n70",
                "sort_order": 72,
                "anchor": {"char_start": n72_start, "char_end": n72_start + 20},
            },
        ]
    }

    markdown = slice_section_markdown_from_payload(content_md, outline_payload, "n71")
    assert markdown is not None
    assert "(6)九阳" in markdown
    assert "不违法分包转包承诺书" not in markdown
    assert "docx-img-457" in markdown

    blocks = section_blocks_for_outline_node(content_md, outline_payload, "n71")
    assert any("九阳" in str(block.get("text") or "") for block in blocks)
    assert any(block.get("type") == "image" for block in blocks)
```

删除旧函数名 `test_slice_section_ignores_wrong_anchor_char_start`（anchor `char_start: 20` 的误导 fixture 不再需要）。

- [ ] **Step 3: Run tests**

Run: `cd backend && .venv/bin/pytest tests/unit/test_doc_chunk_section_slice.py -v`  
Expected: PASS（含 `test_outline_nodes_from_tree_nodes_and_parent_slice` 仍走旧 `slice_section_markdown`，不受影响）

---

## Task 3: `resolve_outline_node_id` 工具函数

**Files:**
- Modify: `backend/src/services/doc_chunk/outline_store.py`
- Create: `backend/tests/unit/test_outline_store.py`（若文件不存在）

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_outline_store.py
import json
from uuid import uuid4

from src.config import Settings
from src.services.doc_chunk.outline_store import (
    persist_outline_node_map,
    resolve_outline_node_id,
)


def test_resolve_outline_node_id_reverse_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "storage_root", str(tmp_path))
    doc_id = uuid4()
    tree_id = uuid4()
    persist_outline_node_map(
        document_id=doc_id,
        outline_node_to_tree_id={"n1": tree_id, "n2": uuid4()},
    )
    assert resolve_outline_node_id(document_id=doc_id, tree_node_id=tree_id) == "n1"
    assert resolve_outline_node_id(document_id=doc_id, tree_node_id=uuid4()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest tests/unit/test_outline_store.py::test_resolve_outline_node_id_reverse_lookup -v`  
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

在 `outline_store.py` 末尾追加：

```python
def resolve_outline_node_id(
    *,
    document_id: UUID,
    tree_node_id: UUID | str,
    storage_root: Path | None = None,
) -> str | None:
    node_map = load_outline_node_map(document_id=document_id, storage_root=storage_root)
    target = str(tree_node_id)
    for outline_node_id, mapped_tree_id in node_map.items():
        if str(mapped_tree_id) == target:
            return outline_node_id
    return None
```

- [ ] **Step 4: Run test**

Run: `cd backend && .venv/bin/pytest tests/unit/test_outline_store.py::test_resolve_outline_node_id_reverse_lookup -v`  
Expected: PASS

---

## Task 4: `get_node_preview` 走 anchor 路径

**Files:**
- Modify: `backend/src/services/knowledge/entry_content_service.py`

- [ ] **Step 1: Update imports**

```python
from src.services.doc_chunk.outline_store import (
    load_outline,
    resolve_outline_node_id,
)
from src.services.doc_chunk.section_slice import (
    PREFACE_NODE_ID,
    PREFACE_TITLE,
    is_preface_node_id,
    slice_section_by_anchor,
)
```

移除 `get_node_preview` 对 `outline_nodes_from_tree_nodes`、`slice_section_markdown` 的使用（若文件其他处仍需要则保留 import）。

- [ ] **Step 2: Replace preview slicing logic**

在 `get_node_preview` 内，`content_md` 加载后增加：

```python
outline_payload = load_outline(document_id=doc_id)
if not outline_payload:
    raise ContentNotAvailableError
```

**前言分支** — 将 `slice_section_markdown(...)` 替换为：

```python
section_md = slice_section_by_anchor(content_md, outline_payload, PREFACE_NODE_ID)
```

**普通节点分支** — 在 `node = nodes_by_id.get(node_uuid)` 之后：

```python
outline_node_id = resolve_outline_node_id(document_id=doc_id, tree_node_id=node_uuid)
if not outline_node_id:
    raise NodeNotFoundError
section_md = slice_section_by_anchor(content_md, outline_payload, outline_node_id)
```

删除对 `slice_section_markdown(content_md, outline_nodes_from_tree_nodes(nodes), node_key)` 的调用。

- [ ] **Step 3: Manual smoke (optional)**

若有本地文档含 outline，调用 preview API 验证；否则依赖 Task 5 单测。

---

## Task 5: Preview 单测补 outline/map fixture

**Files:**
- Modify: `backend/tests/unit/test_knowledge_entry_content.py`

- [ ] **Step 1: Add outline seed helper**

在 `test_knowledge_entry_content.py` 顶部增加 import 与 helper：

```python
from src.services.doc_chunk.outline_store import persist_outline, persist_outline_node_map


def _seed_outline_for_document(
    *,
    document_id,
    parent,
    child=None,
    content_md: str,
    storage_root,
    monkeypatch,
):
    from src.config import Settings

    monkeypatch.setattr(Settings, "storage_root", str(storage_root))
    parent_start = content_md.index("# 第一章")
    nodes = [
        {
            "node_id": "n1",
            "title": parent.title,
            "level": parent.level,
            "parent_id": None,
            "sort_order": parent.sort_order,
            "anchor": {"char_start": parent_start, "char_end": parent_start + 5},
        }
    ]
    mapping = {"n1": parent.node_id}
    if child is not None:
        child_start = content_md.index("## 1.1")
        nodes.append(
            {
                "node_id": "n2",
                "title": child.title,
                "level": child.level,
                "parent_id": "n1",
                "sort_order": child.sort_order,
                "anchor": {"char_start": child_start, "char_end": child_start + 5},
            }
        )
        mapping["n2"] = child.node_id
    persist_outline(document_id=document_id, outline_payload={"nodes": nodes}, storage_root=storage_root)
    persist_outline_node_map(
        document_id=document_id,
        outline_node_to_tree_id=mapping,
        storage_root=storage_root,
    )
```

- [ ] **Step 2: Update `test_get_node_preview_parent_includes_child_content`**

在 `persist_content_md` 之后调用 `_seed_outline_for_document(...)`，并给测试函数加 `monkeypatch` 参数。

- [ ] **Step 3: Update other preview tests that call `get_node_preview`**

对以下测试同样补 outline/map（按各自 content_md 调整 anchor）：
- `test_get_node_preview_excludes_mispositioned_table_assets`
- `test_get_node_preview_returns_preface_content`（前言：第一个节点 anchor 为第一个标题位置）

- [ ] **Step 4: Add regression test — refine level mismatch**

```python
def test_get_node_preview_uses_anchor_not_db_level(db_session, seeded_kb, tmp_path, monkeypatch):
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    content_md = "# 第一章 总则\n\n父节点内容。\n\n## 1.1 范围\n\n子节点内容。\n"
    source = tmp_path / "content.md"
    source.write_text(content_md, encoding="utf-8")
    persist_content_md(document_id=document.document_id, source_path=Path(source))
    _seed_outline_for_document(
        document_id=document.document_id,
        parent=parent,
        child=child,
        content_md=content_md,
        storage_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    # 模拟 tree/refine 把 DB level 改错
    parent.level = 3
    db_session.commit()

    preview = get_node_preview(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=parent.node_id,
    )
    assert "子节点内容" in preview["content_md"]
```

- [ ] **Step 5: Run tests**

Run: `cd backend && .venv/bin/pytest tests/unit/test_knowledge_entry_content.py -v`  
Expected: PASS

---

## Task 6: 全量回归

**Files:** (none — verification only)

- [ ] **Step 1: Run section + preview unit tests**

Run: `cd backend && .venv/bin/pytest tests/unit/test_doc_chunk_section_slice.py tests/unit/test_outline_store.py tests/unit/test_knowledge_entry_content.py -v`  
Expected: PASS

- [ ] **Step 2: Run enrich-related tests**

Run: `cd backend && .venv/bin/pytest tests/unit/test_knowledge_asset_link.py tests/unit/test_knowledge_asset_seed.py -v`  
Expected: PASS（enrich 经 `section_blocks_for_outline_node` 间接使用 anchor 路径）

- [ ] **Step 3: Run integration tests if present**

Run: `cd backend && .venv/bin/pytest tests/integration/test_knowledge_api.py -k preview -v`  
若 integration 测试缺 outline fixture 导致失败，按 Task 5 同样方式补 `_seed_outline_for_document`。

---

## Spec Coverage Checklist

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 新增 `slice_section_by_anchor` | Task 1 |
| `from_payload` 全切换 | Task 2 |
| 父节点含子孙正文 | Task 1 测试 |
| 禁止标题搜索（anchor 路径） | Task 1–2 实现 |
| `get_node_preview` 读 outline + map | Task 3–4 |
| 无 outline → `ContentNotAvailableError` | Task 4 |
| map 缺失 → `NodeNotFoundError` | Task 4 |
| 契约变更单测 | Task 2 |
| preview 单测 fixture | Task 5 |
| enrich 回归 | Task 6 |

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-02-entry-preview-anchor-slice.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派生子 agent，任务间做 review，迭代快

2. **Inline Execution** — 在本会话按 Task 顺序直接实现，每 Task 后 checkpoint

**Which approach?**
