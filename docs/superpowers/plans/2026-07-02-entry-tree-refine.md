# Entry Tree Refine v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 目录刷新只优化 level/parent/sort，标题不变；有章节号走确定性规则，无章节号走 LLM；max_tokens=10k；DashScope 绕过代理。

**Architecture:** 新建 `asset_section_utils` 风格的小模块 `entry_tree_section_utils.py` 负责章节号解析与 pass1；`entry_tree_refine_service.py` 编排 pass1→pass2→安全 merge；`llm_client.py` 增加无代理 opener。

**Tech Stack:** Python 3.11, FastAPI, urllib, pytest.

**Design spec:** `docs/superpowers/specs/2026-07-02-entry-tree-refine-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/services/knowledge/entry_tree_section_utils.py` | **新建** — `parse_section_no`、`infer_structure_from_section_numbers` |
| `backend/src/services/knowledge/entry_tree_refine_service.py` | 重写 prompt、pass1/pass2 编排、title-safe merge |
| `backend/src/services/llm_client.py` | DashScope 无代理 `urlopen` |
| `backend/src/config.py` | `entry_tree_refine_max_tokens=10000` |
| `.env` / `.env.example` | 同步 `ENTRY_TREE_REFINE_MAX_TOKENS=10000` |
| `backend/tests/unit/test_entry_tree_section_utils.py` | **新建** — 章节号解析与 pass1 |
| `backend/tests/unit/test_entry_tree_refine_service.py` | 更新 merge/LLM 相关测试 |
| `backend/tests/unit/test_entry_tree_refine_config.py` | `max_tokens==10000` |

---

## Task 1: 章节号解析与 pass1 确定性推断

**Files:**
- Create: `backend/src/services/knowledge/entry_tree_section_utils.py`
- Create: `backend/tests/unit/test_entry_tree_section_utils.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_entry_tree_section_utils.py
import pytest
from src.services.knowledge.entry_tree_section_utils import (
    parse_section_no,
    infer_structure_from_section_numbers,
)


def test_parse_section_no_dotted():
    assert parse_section_no("2.1合同条款偏离表12") == "2.1"
    assert parse_section_no("8.2.1访问控制和身份验证263") == "8.2.1"


def test_parse_section_no_single():
    assert parse_section_no("8信息安全保护措施262") == "8"


def test_parse_section_no_none():
    assert parse_section_no("评分索引表10") is None
    assert parse_section_no("") is None


def test_infer_structure_parent_and_level():
    nodes = [
        {"node_id": "n1", "title": "2服务偏离表12", "level": 3, "parent_id": None, "sort_order": 0},
        {"node_id": "n2", "title": "2.1合同条款偏离表12", "level": 3, "parent_id": None, "sort_order": 1},
        {"node_id": "n3", "title": "2.2技术条款偏离表13", "level": 3, "parent_id": None, "sort_order": 2},
    ]
    patches = infer_structure_from_section_numbers(nodes)
    by_id = {p["node_id"]: p for p in patches}
    assert by_id["n1"]["level"] == 1
    assert by_id["n1"]["parent_id"] is None
    assert by_id["n2"]["level"] == 2
    assert by_id["n2"]["parent_id"] == "n1"
    assert by_id["n3"]["parent_id"] == "n1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/unit/test_entry_tree_section_utils.py -v`  
Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# backend/src/services/knowledge/entry_tree_section_utils.py
from __future__ import annotations

import re
from typing import Any

_SECTION_NO_RE = re.compile(r"^(\d+(?:\.\d+)*)")


def parse_section_no(title: str) -> str | None:
    text = (title or "").strip()
    match = _SECTION_NO_RE.match(text)
    if not match:
        return None
    return match.group(1)


def _level_from_section_no(section_no: str) -> int:
    return min(max(section_no.count(".") + 1, 1), 8)


def infer_structure_from_section_numbers(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(nodes, key=lambda n: int(n.get("sort_order") or 0))
    section_to_id: dict[str, str] = {}
    patches: list[dict[str, Any]] = []

    for node in ordered:
        node_id = str(node.get("node_id") or "").strip()
        if not node_id:
            continue
        section_no = parse_section_no(str(node.get("title") or ""))
        if not section_no:
            continue
        level = _level_from_section_no(section_no)
        parent_id = None
        if "." in section_no:
            parent_section = section_no.rsplit(".", 1)[0]
            parent_id = section_to_id.get(parent_section)
        patch: dict[str, Any] = {"node_id": node_id, "level": level, "parent_id": parent_id}
        patches.append(patch)
        section_to_id[section_no] = node_id

    return patches
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/unit/test_entry_tree_section_utils.py -v`  
Expected: PASS

---

## Task 2: Title-safe merge 与 prompt 重写

**Files:**
- Modify: `backend/src/services/knowledge/entry_tree_refine_service.py`
- Modify: `backend/tests/unit/test_entry_tree_refine_service.py`

- [ ] **Step 1: Write failing test for title preservation**

```python
def test_merge_outline_nodes_ignores_title_changes():
    from src.services.knowledge.entry_tree_refine_service import _merge_outline_nodes

    outline = {
        "nodes": [{"node_id": "n1", "title": "1投标函11", "level": 3, "parent_id": None, "sort_order": 0}]
    }
    refined = [{"node_id": "n1", "title": "投标函", "level": 1, "parent_id": None, "sort_order": 0}]
    merged = _merge_outline_nodes(outline, refined, preserve_titles=True)
    assert merged["nodes"][0]["title"] == "1投标函11"
    assert merged["nodes"][0]["level"] == 1
```

- [ ] **Step 2: Run test — expect FAIL** (no `preserve_titles` yet)

- [ ] **Step 3: Update `_merge_outline_nodes` and `_SYSTEM_PROMPT`**

- `_merge_outline_nodes(..., preserve_titles: bool = True)` — when True, never apply `title` from patch
- Replace `_SYSTEM_PROMPT` / `_DEFAULT_INSTRUCTION` per spec §5.2（禁止改 t，changes 中 t 必须为 null）
- Update `_compact_change_to_patch` so `title_raw is not None` is ignored when applying (only l/p/s)

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/unit/test_entry_tree_refine_service.py -q -k "not falls_back"`  
Expected: PASS

---

## Task 3: pass1 + pass2 编排

**Files:**
- Modify: `backend/src/services/knowledge/entry_tree_refine_service.py`

- [ ] **Step 1: Write failing test for split targets**

```python
def test_partition_nodes_by_section_no():
    from src.services.knowledge.entry_tree_refine_service import _partition_nodes_by_section_no

    nodes = [
        {"node_id": "n1", "title": "评分索引表10", "level": 3, "parent_id": None, "sort_order": 0},
        {"node_id": "n2", "title": "1投标函11", "level": 3, "parent_id": None, "sort_order": 1},
    ]
    numbered, targets = _partition_nodes_by_section_no(nodes)
    assert len(numbered) == 1 and numbered[0]["node_id"] == "n2"
    assert len(targets) == 1 and targets[0]["node_id"] == "n1"
```

- [ ] **Step 2: Implement `_partition_nodes_by_section_no` and refactor `refine_entry_document_tree`**

Flow in `refine_entry_document_tree`:

1. `repair` + `load_outline`
2. `deterministic_patches = infer_structure_from_section_numbers(nodes)`
3. `outline_payload = _merge_outline_nodes(..., deterministic_patches, preserve_titles=True)`
4. If `targets` non-empty and LLM available:
   - Build user JSON with `numbered_context` + `targets`
   - `chat_completion(..., enable_thinking=False)`
   - Merge LLM patches with `preserve_titles=True`
5. `engine` = `deterministic` | `hybrid` | `llm` per spec §9
6. If no targets, skip LLM entirely

- [ ] **Step 3: Run unit tests**

Run: `cd backend && pytest tests/unit/test_entry_tree_refine_service.py tests/unit/test_entry_tree_section_utils.py -q`  
Expected: PASS

---

## Task 4: max_tokens=10000 与 llm_client 无代理

**Files:**
- Modify: `backend/src/config.py`
- Modify: `backend/src/services/llm_client.py`
- Modify: `.env.example`, `.env`
- Modify: `backend/tests/unit/test_entry_tree_refine_config.py`

- [ ] **Step 1: Update config default**

```python
entry_tree_refine_max_tokens: int = 10000
```

- [ ] **Step 2: Add `_urlopen_without_proxy` in llm_client**

```python
def _open_request(request: urllib.request.Request, *, timeout_sec: int):
    host = urllib.parse.urlparse(request.full_url).hostname or ""
    if host.endswith("dashscope.aliyuncs.com"):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request, timeout=timeout_sec)
    return urllib.request.urlopen(request, timeout=timeout_sec)
```

Use in `chat_completion` instead of bare `urlopen`.

- [ ] **Step 3: Update test**

```python
assert settings.entry_tree_refine_max_tokens == 10000
```

- [ ] **Step 4: Run config test**

Run: `cd backend && pytest tests/unit/test_entry_tree_refine_config.py -v`  
Expected: PASS

---

## Task 5: 手动验证

- [ ] **Step 1: Restart backend**

- [ ] **Step 2: curl tree/refine**

```bash
curl -s -X POST 'http://localhost:8000/api/v1/kbs/f838db41-2c43-45d3-86e9-74494f5ea323/knowledge-chunks/entry/documents/441396fc-56bf-4e55-abfc-8ae12f615de3/tree/refine' \
  -H 'Content-Type: application/json' -H 'X-Operator-Id: admin' -d '{}'
```

Expected: `engine` in `deterministic`|`hybrid`|`llm`；`change_summary` 非 repair 失败文案

- [ ] **Step 3: 标题一致性 spot-check**

```bash
cd backend && python -c "
import json
from pathlib import Path
# compare titles before/after if backup exists, or assert levels not all 3
o=json.loads(Path('data/uploads/documents/441396fc-56bf-4e55-abfc-8ae12f615de3/outline.json').read_text())
levels=set(n['level'] for n in o['nodes'])
print('distinct levels:', sorted(levels))
"
```

Expected: `distinct levels` contains 1, 2, 3 (not only {3})

---

## Plan Self-Review

| Spec § | Task |
|--------|------|
| §4 pass1 章节号 | Task 1 |
| §5 pass2 LLM 无章节号 | Task 3 |
| §6 title-safe merge | Task 2 |
| §7 max_tokens 10k | Task 4 |
| §8 代理绕过 | Task 4 |
| §9 engine 字段 | Task 3 |
| §10 测试 | Tasks 1–4 |
| 不用 content.md | 全计划无 content 引用 ✓ |

No placeholders remain.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-07-02-entry-tree-refine.md`.

**1. Subagent-Driven（推荐）** — 每任务独立 subagent + 审查  
**2. Inline Execution** — 本会话按任务逐步执行  

你想用哪种方式开始实现？
