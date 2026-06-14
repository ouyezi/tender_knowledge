# 铁建标书 E2E 验收 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一键铁建标书验收入口：清业务数据 → 新建 KB → Live 导入解析 → 候选工作台 + 扩展检索 → Integration 回归，全程 JSONL 日志。

**Architecture:** 分层模块化——`reset_business_data.py` 负责 DB TRUNCATE + 存储清理；`workbench.py` / 扩展 `common.py` 承载 Epic4 与检索场景；`run_zhongtie_acceptance.py` 编排 6 个 Phase 并复用现有 `E2EPipelineRunner`。Live 大文件使用 7200s poll + 1800s 上传 timeout。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, urllib (LiveClient), pytest, PostgreSQL 15 (pgvector), 现有 `scripts/lib/e2e/` 框架

**Design doc:** `docs/superpowers/specs/2026-06-14-zhongtie-e2e-acceptance-design.md`

---

## File Map

| 路径 | 职责 | 操作 |
|------|------|------|
| `scripts/lib/e2e/reset_business_data.py` | 业务表 TRUNCATE + STORAGE_ROOT 清理 + URL 安全校验 | Create |
| `scripts/lib/e2e/kb_setup.py` | seed KB 发现 + create_kb API | Create |
| `scripts/lib/e2e/steps/workbench.py` | Epic4 场景 0–9 | Create |
| `scripts/lib/e2e/steps/retrieval_extended.py` | BM25-only / category filter / trace | Create |
| `scripts/lib/e2e/client.py` | LiveClient 可配置 timeout | Modify |
| `scripts/lib/e2e/types.py` | RunContext 扩展 workbench 字段 | Modify |
| `scripts/lib/e2e/logger.py` | log_step 支持 `phase` 字段 | Modify |
| `scripts/run_zhongtie_acceptance.py` | 统一入口 orchestrator | Create |
| `backend/tests/unit/test_reset_business_data.py` | reset 安全 + 表清单 | Create |
| `backend/tests/unit/test_workbench_steps.py` | workbench skip/断言 helpers | Create |
| `backend/tests/unit/test_retrieval_extended.py` | 扩展检索 step 单测 | Create |
| `README.md` | 铁建验收 CLI 文档 | Modify |

---

## Task 1: 业务数据重置模块

**Files:**
- Create: `scripts/lib/e2e/reset_business_data.py`
- Create: `backend/tests/unit/test_reset_business_data.py`

- [ ] **Step 1: 写失败测试 — URL 安全校验**

```python
# backend/tests/unit/test_reset_business_data.py
import pytest

from e2e.reset_business_data import assert_database_url_is_safe, BUSINESS_TABLES


def test_assert_database_url_is_safe_allows_local_postgres():
    assert_database_url_is_safe("postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge")


def test_assert_database_url_is_safe_rejects_remote():
    with pytest.raises(RuntimeError, match="refusing to reset"):
        assert_database_url_is_safe("postgresql+psycopg://user:pass@prod.example.com:5432/db")


def test_business_tables_includes_file_imports():
    assert "file_imports" in BUSINESS_TABLES
    assert "knowledge_units" in BUSINESS_TABLES


def test_business_tables_excludes_knowledge_bases():
    assert "knowledge_bases" not in BUSINESS_TABLES
    assert "chapter_taxonomies" not in BUSINESS_TABLES
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd /Users/tongqianni/xlab/tender_knowledge/backend && ../.venv/bin/pytest tests/unit/test_reset_business_data.py -v`

Expected: FAIL — `ModuleNotFoundError: e2e.reset_business_data`

- [ ] **Step 3: 实现 reset 模块**

```python
# scripts/lib/e2e/reset_business_data.py
from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text

from src.config import Settings
from src.db.session import engine

BUSINESS_TABLES: tuple[str, ...] = (
    "retrieval_feedbacks",
    "retrieval_traces",
    "retrieval_index_entries",
    "retrieval_eval_cases",
    "retrieval_eval_runs",
    "retrieval_eval_sets",
    "candidate_confirm_audit_logs",
    "candidate_knowledge_stubs",
    "candidate_knowledges",
    "knowledge_units",
    "wikis",
    "manual_assets",
    "document_media_assets",
    "document_parse_suggestions",
    "document_tree_nodes",
    "documents",
    "actual_bid_audit_logs",
    "bid_outline_structure_diffs",
    "bid_outline_nodes",
    "bid_outlines",
    "actual_bid_parse_tasks",
    "import_audit_logs",
    "import_tasks",
    "file_purpose_suggestions",
    "file_imports",
    "template_audit_logs",
    "template_structure_diffs",
    "template_publish_snapshots",
    "template_parse_suggestions",
    "template_parse_tasks",
    "template_materials",
    "template_variables",
    "template_rules",
    "template_chapters",
    "templates",
    "template_libraries",
    "generation_snapshots",
    "generation_tasks",
    "chapter_drafts",
    "module_assembly_suggestions",
    "downstream_task_entries",
    "tender_requirement_contexts",
    "chapter_pattern_mining_tasks",
    "chapter_patterns",
    "classification_audit_logs",
    "kb_clone_logs",
)


def assert_database_url_is_safe(database_url: str | None = None) -> None:
    url = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://tender:tender@127.0.0.1:5433/tender_knowledge",
    )
    if url.startswith("sqlite"):
        return
    parsed = urlparse(url.replace("+psycopg", "").replace("+psycopg2", ""))
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if host not in {"127.0.0.1", "localhost"} or port not in {5433, None}:
        raise RuntimeError(f"refusing to reset non-local database: {host}:{port}")


def clear_storage_root(storage_root: Path | None = None) -> int:
    root = Path(storage_root or Settings().storage_root)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return 0
    removed = 0
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed


def reset_business_data(*, storage_root: Path | None = None) -> dict[str, int]:
    assert_database_url_is_safe()
    truncated = 0
    tables_sql = ", ".join(BUSINESS_TABLES)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tables_sql} RESTART IDENTITY CASCADE"))
        truncated = len(BUSINESS_TABLES)
    files_removed = clear_storage_root(storage_root)
    return {"tables_truncated": truncated, "storage_entries_removed": files_removed}
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd /Users/tongqianni/xlab/tender_knowledge/backend && PYTHONPATH=../scripts/lib:.. ../.venv/bin/pytest tests/unit/test_reset_business_data.py -v`

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/e2e/reset_business_data.py backend/tests/unit/test_reset_business_data.py
git commit -m "feat(e2e): add business data reset module with local DB safety guard"
```

---

## Task 2: LiveClient 上传 timeout

**Files:**
- Modify: `scripts/lib/e2e/client.py`
- Test: `backend/tests/unit/test_e2e_client_timeout.py` (Create)

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_e2e_client_timeout.py
from e2e.client import LiveClient


def test_live_client_default_upload_timeout():
    client = LiveClient(base_url="http://127.0.0.1:8000", operator_id="admin")
    assert client.upload_timeout == 1800


def test_live_client_custom_upload_timeout():
    client = LiveClient(base_url="http://127.0.0.1:8000", operator_id="admin", upload_timeout=300)
    assert client.upload_timeout == 300
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest tests/unit/test_e2e_client_timeout.py -v`

Expected: FAIL — `TypeError: unexpected keyword argument 'upload_timeout'` 或 `AttributeError`

- [ ] **Step 3: 修改 LiveClient**

```python
# scripts/lib/e2e/client.py — LiveClient.__init__ 追加参数
class LiveClient:
    def __init__(
        self,
        *,
        base_url: str,
        operator_id: str,
        default_timeout: int = 120,
        upload_timeout: int = 1800,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.operator_id = operator_id
        self.default_timeout = default_timeout
        self.upload_timeout = upload_timeout

    def request(self, method, path, *, json_body=None, files=None, form_data=None, params=None):
        # ... 现有 url/headers 逻辑不变 ...
        timeout = self.upload_timeout if files is not None else self.default_timeout
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                # ... 现有解析逻辑不变 ...
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest tests/unit/test_e2e_client_timeout.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/e2e/client.py backend/tests/unit/test_e2e_client_timeout.py
git commit -m "feat(e2e): configurable LiveClient upload timeout for large files"
```

---

## Task 3: 扩展检索 Steps

**Files:**
- Create: `scripts/lib/e2e/steps/retrieval_extended.py`
- Create: `backend/tests/unit/test_retrieval_extended.py`

- [ ] **Step 1: 写失败测试 — query 提取 helper**

```python
# backend/tests/unit/test_retrieval_extended.py
from e2e.steps.retrieval_extended import _build_search_body


def test_build_search_body_bm25_only():
    body = _build_search_body(query="技术方案", category_id=None, include_trace=False, vector=False)
    assert body["retrieval_options"]["enable_bm25"] is True
    assert body["retrieval_options"]["enable_vector"] is False
    assert "product_category_ids" not in body


def test_build_search_body_with_category_and_trace():
    body = _build_search_body(
        query="测试", category_id="cat-1", include_trace=True, vector=False
    )
    assert body["product_category_ids"] == ["cat-1"]
    assert body["return_options"]["include_trace"] is True
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest tests/unit/test_retrieval_extended.py -v`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 retrieval_extended.py**

```python
# scripts/lib/e2e/steps/retrieval_extended.py
from __future__ import annotations

import time
from typing import Any

from e2e.client import ApiClient, http_meta
from e2e.steps.common import _elapsed, _http_fail, _kb
from e2e.types import PipelineConfig, RunContext, StepResult


def _build_search_body(
    *,
    query: str,
    category_id: str | None,
    include_trace: bool,
    vector: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "query": query,
        "intent": "knowledge_lookup",
        "retrieval_options": {
            "top_k": 10,
            "enable_bm25": True,
            "enable_vector": vector,
        },
    }
    if category_id:
        body["product_category_ids"] = [category_id]
    if include_trace:
        body["return_options"] = {"include_trace": True}
    return body


def step_retrieval_bm25_only(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    path = f"{_kb(cfg)}/retrieval/search"
    body = _build_search_body(query="技术方案", category_id=None, include_trace=False, vector=False)
    resp = api.request("POST", path, json_body=body)
    if not resp.ok:
        return _http_fail("retrieval_bm25_only", start, "POST", path, resp)
    total = resp.data().get("total", 0)
    assertion = {"name": "retrieval_bm25_only", "expected": ">=1", "actual": total}
    if total < 1:
        return StepResult(
            step="retrieval_bm25_only", ok=False, duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp), assertion=assertion,
            error={"type": "AssertionError", "message": "bm25-only returned no hits"},
        )
    return StepResult(
        step="retrieval_bm25_only", ok=True, duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp), assertion=assertion,
    )


def step_retrieval_category_filter(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.category_id or not ctx.published_object_ids:
        return StepResult(
            step="retrieval_category_filter", ok=True, duration_ms=_elapsed(start),
            status="skipped", assertion={"name": "skip", "reason": "missing category or published KU"},
        )
    path = f"{_kb(cfg)}/retrieval/search"
    query = ctx.published_titles[0] if ctx.published_titles else "技术方案"
    body = _build_search_body(query=query, category_id=ctx.category_id, include_trace=False, vector=False)
    resp = api.request("POST", path, json_body=body)
    if not resp.ok:
        return _http_fail("retrieval_category_filter", start, "POST", path, resp)
    items = resp.data().get("items") or []
    hit_ids = {str(i.get("object_id")) for i in items}
    matched = any(oid in hit_ids for oid in ctx.published_object_ids)
    assertion = {"name": "category_filter_hit", "expected": "published in hits", "actual": matched}
    if not matched:
        return StepResult(
            step="retrieval_category_filter", ok=False, duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp), assertion=assertion,
            error={"type": "AssertionError", "message": "category filter missed published KU"},
        )
    return StepResult(
        step="retrieval_category_filter", ok=True, duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp), assertion=assertion,
    )


def step_retrieval_trace(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    path = f"{_kb(cfg)}/retrieval/search"
    body = _build_search_body(query="技术方案", category_id=None, include_trace=True, vector=False)
    resp = api.request("POST", path, json_body=body)
    if not resp.ok:
        return _http_fail("retrieval_trace", start, "POST", path, resp)
    trace_id = resp.data().get("trace_id")
    assertion = {"name": "trace_id_present", "expected": "non-empty", "actual": bool(trace_id)}
    if not trace_id:
        return StepResult(
            step="retrieval_trace", ok=False, duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp), assertion=assertion,
            error={"type": "AssertionError", "message": "missing trace_id"},
        )
    ctx.retrieval_trace_ids.append(str(trace_id))
    return StepResult(
        step="retrieval_trace", ok=True, duration_ms=_elapsed(start),
        context_patch={"retrieval_trace_ids": ctx.retrieval_trace_ids},
        http=http_meta("POST", path, resp), assertion=assertion,
    )
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest tests/unit/test_retrieval_extended.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/e2e/steps/retrieval_extended.py backend/tests/unit/test_retrieval_extended.py
git commit -m "feat(e2e): add extended retrieval steps (bm25, category filter, trace)"
```

---

## Task 4: 候选工作台 Steps（Epic4 Python 化）

**Files:**
- Create: `scripts/lib/e2e/steps/workbench.py`
- Create: `backend/tests/unit/test_workbench_steps.py`

- [ ] **Step 1: 写失败测试 — skip 逻辑**

```python
# backend/tests/unit/test_workbench_steps.py
from e2e.steps.workbench import should_skip_merge, pick_ignore_candidate


def test_should_skip_merge_when_less_than_four():
    assert should_skip_merge(["a", "b", "c"]) is True
    assert should_skip_merge(["a", "b", "c", "d"]) is False


def test_pick_ignore_candidate_excludes_published():
    ids = ["pub-1", "c2", "c3"]
    assert pick_ignore_candidate(ids, published_id="pub-1") == "c3"
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest tests/unit/test_workbench_steps.py -v`

Expected: FAIL

- [ ] **Step 3: 实现 workbench.py**

核心结构（完整文件约 350 行，按 epic4 bash 逐场景移植）：

```python
# scripts/lib/e2e/steps/workbench.py
from __future__ import annotations

import time
from typing import Any

from e2e.client import ApiClient, http_meta
from e2e.steps.common import _elapsed, _first_category_id, _http_fail, _kb, _resolve_taxonomy_and_category
from e2e.types import PipelineConfig, RunContext, StepResult


def should_skip_merge(candidate_ids: list[str]) -> bool:
    return len(candidate_ids) < 4


def pick_ignore_candidate(candidate_ids: list[str], *, published_id: str) -> str | None:
    for cid in reversed(candidate_ids):
        if cid != published_id:
            return cid
    return None


def _skipped(step: str, start: float, reason: str) -> StepResult:
    return StepResult(
        step=step, ok=True, duration_ms=_elapsed(start), status="skipped",
        assertion={"name": "skip", "reason": reason},
    )


def step_wb_pending_exists(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    path = f"{_kb(cfg)}/candidates"
    resp = api.request("GET", path, params={"status": "pending", "import_id": ctx.import_id})
    if not resp.ok:
        return _http_fail("wb_pending_exists", start, "GET", path, resp)
    total = resp.data().get("total", 0)
    ok = total >= 3
    assertion = {"name": "pending_total", "expected": ">=3", "actual": total}
    if not ok:
        return StepResult(
            step="wb_pending_exists", ok=False, duration_ms=_elapsed(start),
            http=http_meta("GET", path, resp), assertion=assertion,
            error={"type": "AssertionError", "message": f"pending total={total}"},
        )
    items = resp.data().get("items") or []
    ctx.candidate_ids = [i["candidate_id"] for i in items]
    return StepResult(
        step="wb_pending_exists", ok=True, duration_ms=_elapsed(start),
        context_patch={"candidate_ids": ctx.candidate_ids},
        http=http_meta("GET", path, resp), assertion=assertion,
    )


# ... 按 spec 表实现 wb_filter_by_import, wb_edit_candidate, wb_publish_single,
# wb_ignore_candidate, wb_merge_candidates, wb_batch_confirm, wb_audit_log,
# wb_retry_publish, wb_retrieval_isolation ...
# wb_publish_single 成功后更新 ctx.published_object_ids / published_titles
# wb_retry_publish: 先 confirm_as=manual_asset 触发失败，再 retry-publish 为 ku


WORKBENCH_STEPS = [
    step_wb_pending_exists,
    # ... 其余 9 个 step 函数引用
]
```

**wb_publish_single 关键逻辑**（与 epic4 场景 3 对齐）：

```python
def step_wb_publish_single(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    _resolve_taxonomy_and_category(api, cfg, ctx)
    if not ctx.candidate_ids:
        return StepResult(step="wb_publish_single", ok=False, duration_ms=_elapsed(start),
                          error={"type": "AssertionError", "message": "no candidates"})
    candidate_id = ctx.candidate_ids[0]
    path = f"{_kb(cfg)}/candidates/{candidate_id}/confirm"
    body: dict[str, Any] = {
        "confirm_as": "ku",
        "knowledge_type": "solution",
        "searchable": True,
        "review_comment": "zhongtie workbench single publish",
    }
    if ctx.category_id:
        body["product_category_ids"] = [ctx.category_id]
    if ctx.taxonomy_id:
        body["chapter_taxonomy_id"] = ctx.taxonomy_id
    resp = api.request("POST", path, json_body=body)
    if not resp.ok:
        return _http_fail("wb_publish_single", start, "POST", path, resp)
    data = resp.data()
    status = data.get("status")
    object_id = data.get("confirmed_object_id")
    ctx.published_object_ids = [str(object_id)] if object_id else []
    title = data.get("title") or "铁建"
    ctx.published_titles = [title]
    assertion = {"name": "published", "status": status, "object_id": object_id}
    ok = status == "published" and bool(object_id)
    return StepResult(
        step="wb_publish_single", ok=ok, duration_ms=_elapsed(start),
        context_patch={"published_object_ids": ctx.published_object_ids, "published_titles": ctx.published_titles},
        http=http_meta("POST", path, resp), assertion=assertion,
        error=None if ok else {"type": "AssertionError", "message": f"status={status}"},
    )
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest tests/unit/test_workbench_steps.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/e2e/steps/workbench.py backend/tests/unit/test_workbench_steps.py
git commit -m "feat(e2e): port Epic4 candidate workbench scenarios to Python steps"
```

---

## Task 5: KB 创建 helper

**Files:**
- Create: `scripts/lib/e2e/kb_setup.py`
- Modify: `backend/tests/unit/test_reset_business_data.py` (追加 find_seed_kb 测试需 DB — 改为纯函数测试)

- [ ] **Step 1: 写失败测试 — kb name 格式**

```python
# backend/tests/unit/test_kb_setup.py
from datetime import datetime, timezone

from e2e.kb_setup import build_kb_name


def test_build_kb_name_prefix():
    name = build_kb_name(now=datetime(2026, 6, 14, 10, 30, 0, tzinfo=timezone.utc))
    assert name.startswith("铁建验收-20260614-")
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest tests/unit/test_kb_setup.py -v`

Expected: FAIL

- [ ] **Step 3: 实现 kb_setup.py**

```python
# scripts/lib/e2e/kb_setup.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from e2e.client import ApiClient
from e2e.types import ApiResponse
from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.knowledge_base import KBStatus, KnowledgeBase


def build_kb_name(*, now: datetime | None = None) -> str:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"铁建验收-{ts}"


def find_seed_kb_id(db: Session, *, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    row = (
        db.query(KnowledgeBase.kb_id)
        .join(ChapterTaxonomy, ChapterTaxonomy.kb_id == KnowledgeBase.kb_id)
        .filter(KnowledgeBase.status == KBStatus.active)
        .order_by(KnowledgeBase.created_at.asc())
        .first()
    )
    if row is None:
        raise RuntimeError("no active KB with chapter_taxonomies found for clone")
    return str(row[0])


def create_kb_via_api(
    api: ApiClient,
    *,
    clone_from_kb_id: str,
    name: str | None = None,
) -> ApiResponse:
    kb_name = name or build_kb_name()
    return api.request(
        "POST",
        "/api/v1/kbs",
        json_body={"name": kb_name, "clone_from_kb_id": clone_from_kb_id},
    )
```

- [ ] **Step 4: 运行测试确认 PASS**

Run: `cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest tests/unit/test_kb_setup.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/e2e/kb_setup.py backend/tests/unit/test_kb_setup.py
git commit -m "feat(e2e): add KB clone helper for zhongtie acceptance"
```

---

## Task 6: 统一入口 run_zhongtie_acceptance.py

**Files:**
- Create: `scripts/run_zhongtie_acceptance.py`
- Modify: `scripts/lib/e2e/logger.py` (支持 `phase` 字段)
- Modify: `scripts/lib/e2e/types.py` (RunContext 追加 `published_candidate_id`)

- [ ] **Step 1: 修改 logger 支持 phase**

```python
# scripts/lib/e2e/logger.py — log_step 追加可选 phase 参数
def log_step(self, result: StepResult, *, context: RunContext | None = None, phase: str | None = None) -> None:
    # ... 现有逻辑 ...
    if phase:
        event["phase"] = phase
```

- [ ] **Step 2: 实现 orchestrator**

```python
#!/usr/bin/env python3
# scripts/run_zhongtie_acceptance.py
"""Zhongtie (铁建) full acceptance: reset -> KB -> import -> workbench -> retrieval -> integration."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

DEFAULT_ZHONGTIE_DOC = Path(
    "/Users/tongqianni/xlab/标书助力/测试招投标文件/标书诊断/中铁/铁建福利商城-标书.docx"
)

from e2e.client import LiveClient
from e2e.integration_harness import run_integration_pipeline
from e2e.kb_setup import create_kb_via_api, find_seed_kb_id
from e2e.logger import JsonlRunLogger
from e2e.reset_business_data import reset_business_data
from e2e.runner import E2EPipelineRunner
from e2e.steps import common
from e2e.steps import retrieval_extended
from e2e.steps import workbench
from e2e.types import PipelineConfig, RunContext, StepResult
from src.db.session import SessionLocal


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Zhongtie E2E acceptance runner")
    p.add_argument("--file", type=Path, default=DEFAULT_ZHONGTIE_DOC)
    p.add_argument("--poll-max", type=int, default=7200)
    p.add_argument("--skip-reset", action="store_true")
    p.add_argument("--skip-integration", action="store_true")
    p.add_argument("--skip-workbench", action="store_true")
    p.add_argument("--keep-services", action="store_true")
    p.add_argument("--log-file", type=Path, default=None)
    p.add_argument("--clone-from-kb-id", default=None)
    p.add_argument("--base-url", default=os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000"))
    p.add_argument("--import-id", default=None, help="Resume live pipeline from existing import")
    p.add_argument("--kb-id", default=None, help="Skip create_kb when resuming")
    return p


def _run_step(logger, fn, ctx, *, phase: str) -> bool:
    result = fn()
    logger.log_step(result, context=ctx, phase=phase)
    return result.ok or result.status == "skipped"


def main() -> int:
    args = build_parser().parse_args()
    if not args.file.exists():
        print(f"file not found: {args.file}")
        return 2

    run_id = str(uuid4())
    log_file = args.log_file or (ROOT / "logs" / f"zhongtie-{run_id}.jsonl")
    logger = JsonlRunLogger(log_file=log_file, run_id=run_id, purpose="actual_bid", mode="live")
    api = LiveClient(base_url=args.base_url, operator_id="admin", upload_timeout=1800)

    steps_total = steps_passed = 0
    failed_step = None
    kb_id = args.kb_id
    ctx = RunContext(kb_id=kb_id or "")

    def track(result_ok: bool, step_name: str) -> None:
        nonlocal steps_total, steps_passed, failed_step
        steps_total += 1
        if result_ok:
            steps_passed += 1
        elif failed_step is None:
            failed_step = step_name

    # Phase 0
    if not args.skip_reset and not args.import_id:
        try:
            stats = reset_business_data()
            logger.log_step(
                StepResult(step="reset_business_data", ok=True, duration_ms=0, context_patch=stats),
                phase="phase0",
            )
            track(True, "reset_business_data")
        except Exception as exc:
            logger.log_exception("reset_business_data", exc)
            logger.log_summary(steps_total=1, steps_passed=0, steps_failed=1,
                               failed_step="reset_business_data", exit_code=2)
            return 2

    # Phase 1
    if not kb_id:
        try:
            with SessionLocal() as db:
                seed_id = find_seed_kb_id(db, explicit=args.clone_from_kb_id)
            resp = create_kb_via_api(api, clone_from_kb_id=seed_id)
            if not resp.ok:
                logger.log_step(
                    StepResult(step="create_kb", ok=False, duration_ms=0,
                               http={"status_code": resp.status_code},
                               error={"message": resp.raw_text[:500]}),
                    phase="phase1",
                )
                logger.log_summary(steps_total=steps_total + 1, steps_passed=steps_passed,
                                   steps_failed=1, failed_step="create_kb", exit_code=2)
                return 2
            kb_id = str(resp.data().get("kb_id"))
            ctx.kb_id = kb_id
            logger.log_step(
                StepResult(step="create_kb", ok=True, duration_ms=0, context_patch={"kb_id": kb_id}),
                phase="phase1",
            )
            track(True, "create_kb")
        except Exception as exc:
            logger.log_exception("create_kb", exc)
            return 2

    # Phase 2 — E2E pipeline (stop at candidates)
    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id=kb_id,
        file_path=args.file,
        mode="live",
        auto_publish_count=0,
        stop_after="candidates",
        poll_max_seconds=args.poll_max,
        keep_services=True,
        base_url=args.base_url,
        resume_import_id=args.import_id,
    )
    runner = E2EPipelineRunner(cfg, api, logger)
    exit2 = runner.run()
    if exit2 != 0:
        logger.log_summary(steps_total=steps_total, steps_passed=steps_passed,
                           steps_failed=1, failed_step="e2e_pipeline", exit_code=exit2)
        if not args.keep_services:
            subprocess.run(["bash", str(ROOT / "scripts/stop.sh")], cwd=str(ROOT), check=False)
        return exit2
    ctx.import_id = runner.ctx.import_id
    ctx.candidate_ids = runner.ctx.candidate_ids
    ctx.taxonomy_id = runner.ctx.taxonomy_id
    ctx.category_id = runner.ctx.category_id

    # Phase 3 — workbench
    if not args.skip_workbench:
        for step_fn in workbench.WORKBENCH_STEPS:
            ok = _run_step(logger, lambda sf=step_fn: sf(api, cfg, ctx), ctx, phase="phase3")
            track(ok, step_fn.__name__)
            if step_fn.__name__ == "step_wb_publish_single" and ok:
                pass  # published_object_ids already in ctx

    # Phase 4 — extended retrieval + existing dynamic/smoke
    retrieval_steps = [
        common.step_retrieval_dynamic,
        common.step_retrieval_smoke,
        retrieval_extended.step_retrieval_bm25_only,
        retrieval_extended.step_retrieval_category_filter,
        retrieval_extended.step_retrieval_trace,
    ]
    for step_fn in retrieval_steps:
        ok = _run_step(logger, lambda sf=step_fn: sf(api, cfg, ctx), ctx, phase="phase4")
        track(ok, step_fn.__name__)

    # Phase 5 — integration regression
    exit_code = 0 if steps_passed == steps_total else 1
    if not args.skip_integration:
        int_log = log_file.with_name(log_file.stem + "-integration.jsonl")
        int_cfg = PipelineConfig(
            purpose="actual_bid",
            kb_id="placeholder",
            file_path=ROOT / "backend/tests/fixtures/sample-actual-bid.docx",
            mode="integration",
            stop_after="retrieval",
            poll_max_seconds=30,
            log_file=int_log,
        )
        int_exit = run_integration_pipeline(int_cfg, monkeypatch_chapter_rules=_patch_chapter_rules)
        logger.log_step(
            StepResult(step="integration_regression", ok=int_exit == 0, duration_ms=0,
                       assertion={"exit_code": int_exit}),
            phase="phase5",
        )
        if int_exit != 0:
            exit_code = 1

    if not args.keep_services:
        subprocess.run(["bash", str(ROOT / "scripts/stop.sh")], cwd=str(ROOT), check=False)

    logger.log_summary(
        steps_total=steps_total, steps_passed=steps_passed,
        steps_failed=steps_total - steps_passed, failed_step=failed_step, exit_code=exit_code,
    )
    return exit_code


def _patch_chapter_rules(module) -> None:
    module._CACHE = {
        "default": {"candidate_type": "ku", "suggested_knowledge_type": "solution"},
        "rules": {},
    }


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 补全 workbench.WORKBENCH_STEPS 列表**（Task 4 中 10 个 step 全部注册）

- [ ] **Step 4: 本地 smoke — integration only**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge
.venv/bin/python scripts/run_zhongtie_acceptance.py \
  --skip-reset --skip-workbench --skip-integration \
  --file backend/tests/fixtures/sample-actual-bid.docx \
  --poll-max 60 \
  --kb-id $(.venv/bin/python -c "
from src.db.session import SessionLocal
from src.models.knowledge_base import KnowledgeBase
with SessionLocal() as db:
    kb = db.query(KnowledgeBase).first()
    print(kb.kb_id if kb else '')
")
```

Expected: 若本地有 KB 且服务运行，pipeline 阶段产生 JSONL；无服务则 preflight FAIL exit 2。

- [ ] **Step 5: Commit**

```bash
git add scripts/run_zhongtie_acceptance.py scripts/lib/e2e/logger.py scripts/lib/e2e/types.py
git commit -m "feat(e2e): add zhongtie acceptance orchestrator with 6 phases"
```

---

## Task 7: README 文档

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 E2E 章节后追加铁建验收说明**

```markdown
### 铁建标书全链路验收

```bash
# 完整验收（重置 DB + 铁建 1GB 文件 + 工作台 + 检索 + integration 回归）
.venv/bin/python scripts/run_zhongtie_acceptance.py --keep-services

# 续跑（跳过 reset，从已有 import 继续）
.venv/bin/python scripts/run_zhongtie_acceptance.py \
  --skip-reset --kb-id <KB_UUID> --import-id <IMPORT_UUID> --keep-services

# 仅 integration 回归
.venv/bin/python scripts/run_zhongtie_acceptance.py --skip-reset --skip-workbench --file backend/tests/fixtures/sample-actual-bid.docx
```

日志：`logs/zhongtie-<run_id>.jsonl`；Integration 回归：`logs/zhongtie-<run_id>-integration.jsonl`。

**注意**：铁建 docx 约 1GB，默认 `--poll-max 7200`（2 小时）；需本地 Postgres + LLM 可用。
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add zhongtie E2E acceptance CLI to README"
```

---

## Task 8: Live 全链路手动验收

**前置条件：**
```bash
docker compose up -d postgres
./scripts/start.sh   # 或 SKIP_FRONTEND=1
```

- [ ] **Step 1: 运行完整验收**

Run:
```bash
cd /Users/tongqianni/xlab/tender_knowledge
.venv/bin/python scripts/run_zhongtie_acceptance.py --keep-services 2>&1 | tee logs/zhongtie-live-run.log
```

Expected:
- Phase 0: `reset_business_data` ok
- Phase 1: `create_kb` 返回新 kb_id
- Phase 2: upload → parse → candidates（可能 30min–2h）
- Phase 3: workbench 10 场景 mostly ok（候选不足时 merge/retry skip）
- Phase 4: retrieval 5 场景 ok
- Phase 5: integration exit 0
- 最后一行 JSONL: `"step":"run_summary","exit_code":0`

- [ ] **Step 2: 失败时修复并重跑**

若 Phase 2 失败：
```bash
.venv/bin/python scripts/run_zhongtie_acceptance.py \
  --skip-reset --kb-id <KB_UUID> --import-id <IMPORT_UUID> \
  --from-step parse --keep-services
```
（需在 orchestrator 追加 `--from-step` 透传至 PipelineConfig，若 Task 6 未包含则补一个小 commit）

若不可修复（OOM/超时）：
- JSONL 中应有 `"error":{"blocked":true,"reason":"..."}`
- exit 1，不生成 Markdown 报告

- [ ] **Step 3: 运行 unit + integration 测试套件**

Run:
```bash
cd backend && PYTHONPATH=../scripts/lib ../.venv/bin/pytest \
  tests/unit/test_reset_business_data.py \
  tests/unit/test_e2e_client_timeout.py \
  tests/unit/test_retrieval_extended.py \
  tests/unit/test_workbench_steps.py \
  tests/unit/test_kb_setup.py \
  tests/integration/test_e2e_pipeline_flow.py -v
```

Expected: ALL PASS

---

## Spec Coverage Checklist

| Spec 章节 | 对应 Task |
|-----------|-----------|
| Phase 0 业务重置 | Task 1 |
| Phase 1 新建 KB | Task 5, 6 |
| Phase 2 Live E2E | Task 6 |
| Phase 3 工作台 0–9 | Task 4, 6 |
| Phase 4 扩展检索 | Task 3, 6 |
| Phase 5 Integration | Task 6, 8 |
| 1GB timeout | Task 2, 6 |
| JSONL only | Task 6 (logger) |
| 安全约束 localhost:5433 | Task 1 |

**已知风险（非阻塞，Task 8 处理）：**
- 铁建 docx ~1GB，解析可能超出 7200s — JSONL 记 `blocked=true`
- `config.max_file_size_docx_mb=50` 若上传路由后续启用校验需调 `.env`；当前上传无硬限制但需在 preflight 打日志警告

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-14-zhongtie-e2e-acceptance.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派独立 subagent，Task 间 review，快速迭代

2. **Inline Execution** — 本会话按 Task 顺序直接实现，checkpoint 处暂停 review

**Which approach?**
