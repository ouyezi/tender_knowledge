# E2E 导入→知识发布→检索 验收脚本 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 `scripts/e2e_pipeline_test.py`，对 actual_bid / template_file 跑通「导入→解析→自动发布→检索断言」全链路，输出 agent 可读的 JSONL 日志。

**Architecture:** Python 编排器 + `scripts/lib/e2e/` 模块化 Step 库；`ApiClient` 协议统一 Live HTTP 与 Integration TestClient；Live 模式自动 `SKIP_FRONTEND=1 scripts/start.sh`；解析 poll 超时走 runner fallback（复用 epic3 模式）。

**Tech Stack:** Python 3.11, urllib.request, FastAPI TestClient, pytest, subprocess, SQLAlchemy SessionLocal（fallback 步骤）

**Design doc:** `docs/superpowers/specs/2026-06-14-e2e-import-retrieval-pipeline-design.md`

---

## File Map

| 路径 | 职责 |
|------|------|
| `scripts/e2e_pipeline_test.py` | CLI 入口、argparse、teardown |
| `scripts/lib/e2e/__init__.py` | 包导出 |
| `scripts/lib/e2e/types.py` | `PipelineConfig`, `RunContext`, `ApiResponse`, `StepResult` |
| `scripts/lib/e2e/logger.py` | `JsonlRunLogger`：jsonl 写入 + 终端一行摘要 |
| `scripts/lib/e2e/client.py` | `LiveClient`, `IntegrationClient` |
| `scripts/lib/e2e/runner.py` | `E2EPipelineRunner`：步骤编排、fail-fast、run_summary |
| `scripts/lib/e2e/fallback.py` | actual_bid / template parse runner 同步执行 |
| `scripts/lib/e2e/steps/common.py` | preflight, upload, confirm, list_candidates, auto_publish, retrieval |
| `scripts/lib/e2e/steps/actual_bid.py` | parse poll, wizard confirm, taxonomy backfill, candidate generate |
| `scripts/lib/e2e/steps/template_file.py` | template parse poll, confirm |
| `scripts/lib/e2e/taxonomy_backfill.py` | 参数化自 bootstrap-dingxin-candidates 的 heading 映射 |
| `backend/tests/unit/test_e2e_logger.py` | logger 单元测试 |
| `backend/tests/unit/test_e2e_runner_summary.py` | runner 汇总逻辑单元测试 |
| `backend/tests/integration/test_e2e_pipeline_flow.py` | integration 模式全链路 |

**Import 路径约定：** 所有 `scripts/lib/e2e` 模块在文件头加入：

```python
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]  # repo root from scripts/lib/e2e/*.py
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))
if str(ROOT / "scripts" / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "lib"))
```

---

## Phase P0 — 基建（logger + types + client）

### Task P0-1: 类型与 RunContext

**Files:**
- Create: `scripts/lib/e2e/__init__.py`
- Create: `scripts/lib/e2e/types.py`
- Test: `backend/tests/unit/test_e2e_types.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_e2e_types.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))

from e2e.types import PipelineConfig, RunContext


def test_run_context_merge():
    ctx = RunContext(kb_id="kb-1")
    ctx.merge(import_id="imp-1", candidate_ids=["c1"])
    assert ctx.import_id == "imp-1"
    assert ctx.candidate_ids == ["c1"]
    d = ctx.to_dict()
    assert d["kb_id"] == "kb-1"


def test_pipeline_config_defaults():
    cfg = PipelineConfig(purpose="actual_bid", kb_id="kb-1", file_path=Path("a.docx"))
    assert cfg.mode == "live"
    assert cfg.auto_publish_count == 1
    assert cfg.poll_max_seconds == 600
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `cd backend && ../.venv/bin/python -m pytest tests/unit/test_e2e_types.py -v`  
Expected: FAIL `ModuleNotFoundError: e2e`

- [ ] **Step 3: 实现 types.py**

```python
# scripts/lib/e2e/types.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


Purpose = Literal["actual_bid", "template_file"]
RunMode = Literal["live", "integration"]


@dataclass
class PipelineConfig:
    purpose: Purpose
    kb_id: str
    file_path: Path
    mode: RunMode = "live"
    auto_publish_count: int = 1
    poll_max_seconds: int = 600
    poll_interval_seconds: float = 5.0
    keep_services: bool = False
    log_file: Path | None = None
    operator_id: str = "admin"
    base_url: str = "http://127.0.0.1:8000"


@dataclass
class ApiResponse:
    status_code: int
    json: dict[str, Any]
    raw_text: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def data(self) -> dict[str, Any]:
        payload = self.json.get("data")
        return payload if isinstance(payload, dict) else {}


@dataclass
class StepResult:
    step: str
    ok: bool
    duration_ms: int
    context_patch: dict[str, Any] = field(default_factory=dict)
    http: dict[str, Any] | None = None
    assertion: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    status: str = "ok"  # ok | failed | warning | skipped


@dataclass
class RunContext:
    kb_id: str
    import_id: str | None = None
    document_id: str | None = None
    parse_task_id: str | None = None
    bid_outline_id: str | None = None
    template_id: str | None = None
    candidate_ids: list[str] = field(default_factory=list)
    published_object_ids: list[str] = field(default_factory=list)
    published_titles: list[str] = field(default_factory=list)
    retrieval_trace_ids: list[str] = field(default_factory=list)
    query_used: str | None = None
    taxonomy_id: str | None = None
    category_id: str | None = None

    def merge(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if not hasattr(self, key):
                continue
            current = getattr(self, key)
            if isinstance(current, list) and isinstance(value, list):
                setattr(self, key, [*current, *value])
            else:
                setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kb_id": self.kb_id,
            "import_id": self.import_id,
            "document_id": self.document_id,
            "parse_task_id": self.parse_task_id,
            "bid_outline_id": self.bid_outline_id,
            "template_id": self.template_id,
            "candidate_ids": self.candidate_ids,
            "published_object_ids": self.published_object_ids,
            "published_titles": self.published_titles,
            "retrieval_trace_ids": self.retrieval_trace_ids,
            "query_used": self.query_used,
            "taxonomy_id": self.taxonomy_id,
            "category_id": self.category_id,
        }
```

- [ ] **Step 4: 运行测试 PASS**

Run: `cd backend && ../.venv/bin/python -m pytest tests/unit/test_e2e_types.py -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/e2e/types.py scripts/lib/e2e/__init__.py backend/tests/unit/test_e2e_types.py
git commit -m "feat(e2e): add pipeline types and RunContext"
```

---

### Task P0-2: JsonlRunLogger

**Files:**
- Create: `scripts/lib/e2e/logger.py`
- Test: `backend/tests/unit/test_e2e_logger.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_e2e_logger.py
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))

from e2e.logger import JsonlRunLogger
from e2e.types import StepResult


def test_logger_writes_jsonl_and_summary(tmp_path):
    log_path = tmp_path / "run.jsonl"
    logger = JsonlRunLogger(
        log_file=log_path,
        run_id="run-1",
        purpose="actual_bid",
        mode="integration",
    )
    logger.log_step(
        StepResult(step="upload", ok=True, duration_ms=10, context_patch={"import_id": "x"})
    )
    logger.log_summary(steps_total=1, steps_passed=1, steps_failed=0, failed_step=None, exit_code=0)
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["step"] == "upload"
    assert first["status"] == "ok"
    assert first["context"]["import_id"] == "x"
    summary = json.loads(lines[1])
    assert summary["step"] == "run_summary"
    assert summary["exit_code"] == 0
```

- [ ] **Step 2: 运行 FAIL**

Run: `cd backend && ../.venv/bin/python -m pytest tests/unit/test_e2e_logger.py -v`

- [ ] **Step 3: 实现 logger.py**

```python
# scripts/lib/e2e/logger.py
from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from e2e.types import RunContext, StepResult


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class JsonlRunLogger:
    def __init__(self, *, log_file: Path, run_id: str, purpose: str, mode: str) -> None:
        self.log_file = log_file
        self.run_id = run_id
        self.purpose = purpose
        self.mode = mode
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._context: dict[str, Any] = {}

    def update_context(self, patch: dict[str, Any]) -> None:
        self._context.update({k: v for k, v in patch.items() if v is not None})

    def log_step(self, result: StepResult, *, context: RunContext | None = None) -> None:
        if context is not None:
            self.update_context(context.to_dict())
        if result.context_patch:
            self.update_context(result.context_patch)
        status = "failed" if not result.ok else result.status
        event: dict[str, Any] = {
            "ts": _utc_now(),
            "run_id": self.run_id,
            "step": result.step,
            "status": status,
            "duration_ms": result.duration_ms,
            "purpose": self.purpose,
            "mode": self.mode,
            "context": dict(self._context),
        }
        if result.http:
            event["http"] = result.http
        if result.assertion:
            event["assertion"] = result.assertion
        if result.error:
            event["error"] = result.error
        self._append(event)
        label = "FAILED" if not result.ok else status.upper()
        print(f"[{result.step}] {label} ({result.duration_ms}ms)")

    def log_exception(self, step: str, exc: BaseException, *, duration_ms: int = 0) -> None:
        self.log_step(
            StepResult(
                step=step,
                ok=False,
                duration_ms=duration_ms,
                status="failed",
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
        )

    def log_summary(
        self,
        *,
        steps_total: int,
        steps_passed: int,
        steps_failed: int,
        failed_step: str | None,
        exit_code: int,
    ) -> None:
        event = {
            "ts": _utc_now(),
            "run_id": self.run_id,
            "step": "run_summary",
            "status": "ok" if exit_code == 0 else "failed",
            "purpose": self.purpose,
            "mode": self.mode,
            "steps_total": steps_total,
            "steps_passed": steps_passed,
            "steps_failed": steps_failed,
            "failed_step": failed_step,
            "log_file": str(self.log_file),
            "exit_code": exit_code,
        }
        self._append(event)

    def _append(self, event: dict[str, Any]) -> None:
        with self.log_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: pytest PASS**

- [ ] **Step 5: Commit** `feat(e2e): add JsonlRunLogger`

---

### Task P0-3: ApiClient（Live + Integration）

**Files:**
- Create: `scripts/lib/e2e/client.py`
- Test: `backend/tests/unit/test_e2e_client.py`

- [ ] **Step 1: 写 IntegrationClient 测试（用 TestClient fixture 模式）**

```python
# backend/tests/unit/test_e2e_client.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))
sys.path.insert(0, str(ROOT))

from e2e.client import IntegrationClient


def test_integration_client_health(client, seeded_kb):
    api = IntegrationClient(client, operator_id="admin")
    resp = api.request("GET", "/health")
    assert resp.ok
    assert resp.json.get("status") == "ok"


def test_integration_client_kb_get(client, seeded_kb):
    api = IntegrationClient(client, operator_id="admin")
    resp = api.request("GET", f"/api/v1/kbs/{seeded_kb.kb_id}")
    assert resp.ok
```

- [ ] **Step 2: FAIL → 实现 client.py**

```python
# scripts/lib/e2e/client.py
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from e2e.types import ApiResponse


class ApiClient(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResponse: ...


def _excerpt(text: str, limit: int = 2048) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


class LiveClient:
    def __init__(self, *, base_url: str, operator_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.operator_id = operator_id

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResponse:
        raise NotImplementedError("multipart upload implemented in Task P1")


class IntegrationClient:
    def __init__(self, test_client, *, operator_id: str) -> None:
        self._client = test_client
        self.operator_id = operator_id

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResponse:
        headers = {"X-Operator-Id": self.operator_id}
        kwargs: dict[str, Any] = {"headers": headers}
        if params:
            kwargs["params"] = params
        if json_body is not None:
            kwargs["json"] = json_body
        if files is not None:
            kwargs["files"] = files
        resp = self._client.request(method, path, **kwargs)
        try:
            payload = resp.json()
        except Exception:
            payload = {}
        return ApiResponse(status_code=resp.status_code, json=payload, raw_text=resp.text)

    def http_meta(self, method: str, path: str, resp: ApiResponse) -> dict[str, Any]:
        return {
            "method": method,
            "path": path,
            "status_code": resp.status_code,
            "response_excerpt": _excerpt(resp.raw_text),
        }
```

- [ ] **Step 3: 补全 LiveClient.request（JSON GET/POST）与 http_meta 辅助函数**

- [ ] **Step 4: pytest PASS**

- [ ] **Step 5: Commit** `feat(e2e): add Live and Integration API clients`

---

## Phase P1 — 共用步骤（common steps）

### Task P1-1: preflight + upload + confirm_import

**Files:**
- Create: `scripts/lib/e2e/steps/__init__.py`
- Create: `scripts/lib/e2e/steps/common.py`
- Test: `backend/tests/unit/test_e2e_common_steps.py`

- [ ] **Step 1: 写 integration 测试 upload+confirm**

```python
# backend/tests/unit/test_e2e_common_steps.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))
sys.path.insert(0, str(ROOT))

from e2e.client import IntegrationClient
from e2e.steps.common import step_confirm_import, step_preflight, step_upload
from e2e.types import PipelineConfig, RunContext
from src.services.import_task_runner import run_post_upload


def test_preflight_and_upload_confirm(client, seeded_kb, sample_docx_path, db_session):
    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id=str(seeded_kb.kb_id),
        file_path=sample_docx_path,
        mode="integration",
    )
    ctx = RunContext(kb_id=cfg.kb_id)
    api = IntegrationClient(client, operator_id="admin")

    pre = step_preflight(api, cfg, ctx)
    assert pre.ok

    up = step_upload(api, cfg, ctx)
    assert up.ok
    assert ctx.import_id
    run_post_upload(db_session, __import__("uuid").UUID(ctx.import_id))

    conf = step_confirm_import(api, cfg, ctx)
    assert conf.ok
```

- [ ] **Step 2: 实现 common.py 中三个 step 函数**

关键实现要点：

```python
# step_preflight: GET /health; GET /api/v1/kbs/{kb_id}
# step_upload: IntegrationClient files=; LiveClient multipart via urllib
# step_confirm_import:
#   GET file-imports/{id} 取 version
#   POST confirm json={
#     expected_version, file_purpose: cfg.purpose,
#     product_category_ids: [], enter_parsing: True
#   }
#   context 写入 import_id, parse_task_id (actual_bid_parse_task_id)
```

Live multipart 参考 `epic6_live_acceptance.py` 不适用；参考 `test_file_import_upload.py`：

```python
files = {"file": (cfg.file_path.name, cfg.file_path.open("rb"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
```

- [ ] **Step 3: pytest PASS**

- [ ] **Step 4: Commit** `feat(e2e): add preflight upload confirm steps`

---

### Task P1-2: auto_publish + retrieval 断言

**Files:**
- Modify: `scripts/lib/e2e/steps/common.py`
- Modify: `backend/tests/contract/test_candidates_list.py`（复用 `_seed_active_taxonomy` / `_seed_active_category`）
- Test: 扩展 `backend/tests/integration/test_e2e_pipeline_flow.py`（先写 publish+retrieval 部分）

- [ ] **Step 1: 写 retrieval 断言失败测试**

在 integration 测试中 seed 已发布 KU + index entry（复用 `test_retrieval_search.py` 模式），调用：

```python
from e2e.steps.common import step_retrieval_dynamic, step_retrieval_smoke

ctx.published_object_ids = [str(ku.ku_id)]
ctx.published_titles = [ku.title]
dyn = step_retrieval_dynamic(api, cfg, ctx)
assert dyn.ok
smoke = step_retrieval_smoke(api, cfg, ctx)
assert smoke.ok
```

- [ ] **Step 2: 实现函数**

```python
def _extract_query(title: str) -> str:
    cleaned = "".join(ch for ch in title if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    return cleaned[:8] if len(cleaned) >= 2 else "技术方案"


def step_list_candidates(...):
    # GET .../candidates?status=pending&import_id=
    # assert total >= 1; ctx.candidate_ids = [item["candidate_id"] ...]

def step_auto_publish(...):
    # 取前 auto_publish_count 个 candidate_id
    # actual_bid: confirm_as=ku, knowledge_type=solution, 需 taxonomy_id/category_id
    #   若无 taxonomy：GET chapter-taxonomies?page_size=1
    # template_file: confirm_as=template_chapter，失败降级 ku + warning
    # ctx.published_object_ids.append(confirmed_object_id)

def step_retrieval_dynamic(...):
    query = _extract_query(ctx.published_titles[0])
    ctx.query_used = query
    POST .../retrieval/search {"query": query, "intent": "knowledge_lookup", "retrieval_options": {"top_k": 10}}
    assert any hit.object_id in ctx.published_object_ids

def step_retrieval_smoke(...):
    POST query="技术方案"; assert len(hits) >= 1
```

- [ ] **Step 3: pytest PASS**

- [ ] **Step 4: Commit** `feat(e2e): add publish and retrieval assertion steps`

---

## Phase P2 — actual_bid 分支

### Task P2-1: parse poll + wizard confirm

**Files:**
- Create: `scripts/lib/e2e/steps/actual_bid.py`
- Create: `scripts/lib/e2e/fallback.py`
- Test: 扩展 `test_e2e_pipeline_flow.py`

- [ ] **Step 1: 写 integration 测试（upload→confirm→run_actual_bid_parse_pending→steps）**

```python
from src.services.actual_bid_parse_runner import run_actual_bid_parse_pending
from e2e.steps.actual_bid import step_parse_poll, step_parse_wizard_confirm

run_actual_bid_parse_pending(db_session)
poll = step_parse_poll(api, cfg, ctx, run_fallback=lambda: None)
assert poll.ok
wiz = step_parse_wizard_confirm(api, cfg, ctx)
assert wiz.ok
```

`step_parse_wizard_confirm` 复用 `test_actual_bid_flow._build_confirm_outline_nodes_payload` 逻辑（搬到 e2e 模块内联查询 API：`GET bid-outlines/{id}/nodes`）。

- [ ] **Step 2: 实现 step_parse_poll**

```python
# 轮询 GET /actual-bid-parse/tasks/{parse_task_id}
# ready|confirmed -> ok; failed -> fail
# 超时调用 run_fallback() 一次再 poll
# ctx.document_id, ctx.bid_outline_id 从 task data 填充
```

- [ ] **Step 3: 实现 fallback.py actual_bid 部分**

```python
def run_actual_bid_fallback(import_id: str) -> None:
    from uuid import UUID
    from src.db.session import SessionLocal
    from src.models.downstream_task_entry import DownstreamTaskEntry, DownstreamTaskStatus, DownstreamTaskType
    from src.services.actual_bid_parse_runner import _run_entry
    with SessionLocal() as db:
        entry = db.query(DownstreamTaskEntry).filter(...).first()
        if entry:
            entry.status = DownstreamTaskStatus.claimed
            entry.claimed_by = "e2e-pipeline"
            db.flush()
            _run_entry(db, entry)
            db.commit()
```

- [ ] **Step 4: pytest PASS**

- [ ] **Step 5: Commit** `feat(e2e): add actual_bid parse steps and fallback`

---

### Task P2-2: taxonomy backfill + candidate generate

**Files:**
- Create: `scripts/lib/e2e/taxonomy_backfill.py`
- Modify: `scripts/lib/e2e/steps/actual_bid.py`

- [ ] **Step 1: 从 bootstrap-dingxin-candidates.py 提取 `_should_map_heading`、`_ensure_taxonomy` 到 taxonomy_backfill.py（参数 kb_id, import_id, document_id）**

- [ ] **Step 2: step_candidate_ensure**

```python
def step_candidate_ensure(db_session, cfg, ctx):
    # GET candidates pending; if total==0:
    #   taxonomy_backfill(db, kb_id, document_id)
    #   candidate_generate_service.generate_for_document(...)
    # 刷新 ctx.candidate_ids
```

Integration 模式传入 `db_session`；Live 模式在 fallback 模块用 SessionLocal。

- [ ] **Step 3: 单元测试 taxonomy_backfill（mock heading 节点）**

- [ ] **Step 4: Commit** `feat(e2e): add taxonomy backfill and candidate ensure`

---

## Phase P3 — template_file 分支

### Task P3-1: template parse poll + confirm

**Files:**
- Create: `scripts/lib/e2e/steps/template_file.py`
- Modify: `scripts/lib/e2e/fallback.py`

- [ ] **Step 1: 写测试（seed confirmed import + run_template_parse_pending）**

```python
from src.services.template_parse_runner import run_template_parse_pending
from e2e.steps.template_file import step_template_parse_poll, step_template_parse_confirm

run_template_parse_pending(db_session)
assert step_template_parse_poll(api, cfg, ctx, run_fallback=lambda: None).ok
assert step_template_parse_confirm(api, cfg, ctx).ok
```

- [ ] **Step 2: 实现 poll**

```python
# GET /template-parse/tasks/{id}
# status parse_ready -> ok; ctx.template_id
```

- [ ] **Step 3: 实现 confirm**

```python
# GET task detail + suggestion
# POST /template-parse/tasks/{id}/confirm
# body 参考 test_template_parse_confirm.py 成功用例（library_name, chapter_tree, materials, candidates）
```

- [ ] **Step 4: template fallback** — `run_template_parse_pending` 或 `_run_entry` 同步

- [ ] **Step 5: Commit** `feat(e2e): add template_file parse steps`

---

## Phase P4 — Runner 编排 + CLI

### Task P4-1: E2EPipelineRunner

**Files:**
- Create: `scripts/lib/e2e/runner.py`
- Test: `backend/tests/unit/test_e2e_runner_summary.py`

- [ ] **Step 1: 测试 fail-fast 与 run_summary**

```python
def test_runner_fail_fast_records_failed_step():
    # mock step 返回 ok=False on step 2
    # assert steps_passed==1, failed_step=="step2", exit_code==1
```

- [ ] **Step 2: 实现 runner.run()**

```python
class E2EPipelineRunner:
    def __init__(self, cfg, api, logger, *, db_session=None): ...

    def run(self) -> int:
        steps = [("preflight", ...), ("upload", ...), ...]
        if cfg.mode == "live":
            steps.insert(0, ("bootstrap_services", ...))
        if cfg.purpose == "actual_bid":
            steps.extend([("parse_poll", ...), ("parse_wizard_confirm", ...), ("candidate_ensure", ...)])
        else:
            steps.extend([("template_parse_poll", ...), ("template_parse_confirm", ...)])
        steps.extend([("list_candidates", ...), ("auto_publish", ...),
                      ("retrieval_dynamic", ...), ("retrieval_smoke", ...)])
        # fail-fast loop; logger.log_step each; log_summary at end
```

- [ ] **Step 3: Commit** `feat(e2e): add E2EPipelineRunner orchestration`

---

### Task P4-2: CLI 入口

**Files:**
- Create: `scripts/e2e_pipeline_test.py`

- [ ] **Step 1: argparse + 默认 fixture 路径**

```python
DEFAULT_FIXTURES = {
    "actual_bid": ROOT / "backend/tests/fixtures/sample-actual-bid.docx",
    "template_file": ROOT / "backend/tests/fixtures/sample-template.docx",
}
```

- [ ] **Step 2: live 模式主流程**

```python
def main():
    cfg = build_config(args)
    log_file = cfg.log_file or ROOT / "logs" / f"e2e-{uuid4()}.jsonl"
    if cfg.mode == "integration":
        return run_integration_mode(cfg, log_file)
    subprocess.run(["bash", str(ROOT / "scripts/start.sh")], env={**os.environ, "SKIP_FRONTEND": "1"}, check=True)
    try:
        api = LiveClient(base_url=cfg.base_url, operator_id=cfg.operator_id)
        runner = E2EPipelineRunner(cfg, api, logger)
        return runner.run()
    finally:
        if not cfg.keep_services:
            subprocess.run(["bash", str(ROOT / "scripts/stop.sh")], check=False)
```

- [ ] **Step 3: integration 模式**

```python
def run_integration_mode(cfg, log_file):
    # 内嵌：setup TestClient（复制 conftest 最小 setup 或 subprocess pytest 单文件）
    # 推荐：pytest.main 包装 — 但为保持单入口，使用 fastapi TestClient + db_engine fixture 逻辑抽取到 scripts/lib/e2e/integration_harness.py
```

创建 `scripts/lib/e2e/integration_harness.py`：从 conftest 复制 `db_engine`/`client`/`seeded_kb`/`storage_root_tmp` 最小集，供 CLI integration 模式调用。

- [ ] **Step 4: 手动 smoke**

Run: `.venv/bin/python scripts/e2e_pipeline_test.py --mode integration --purpose actual_bid --kb-id <from test>`

注：integration 模式 kb_id 由 harness 创建并覆盖 cfg.kb_id。

- [ ] **Step 5: Commit** `feat(e2e): add e2e_pipeline_test CLI entrypoint`

---

## Phase P5 — Integration 全链路测试

### Task P5-1: test_e2e_pipeline_flow.py

**Files:**
- Create: `backend/tests/integration/test_e2e_pipeline_flow.py`

- [ ] **Step 1: 全链路测试 actual_bid**

```python
def test_e2e_pipeline_integration_actual_bid(client, db_session, seeded_kb, sample_docx_path, tmp_path, monkeypatch):
    monkeypatch.setattr(chapter_candidate_rules, "_CACHE", {...})  # 同 test_actual_bid_flow
    cfg = PipelineConfig(
        purpose="actual_bid",
        kb_id=str(seeded_kb.kb_id),
        file_path=sample_docx_path,
        mode="integration",
        log_file=tmp_path / "run.jsonl",
        auto_publish_count=1,
    )
    api = IntegrationClient(client, operator_id="admin")
    logger = JsonlRunLogger(...)
    runner = E2EPipelineRunner(cfg, api, logger, db_session=db_session)
    assert runner.run() == 0
    lines = cfg.log_file.read_text().strip().splitlines()
    assert "run_summary" in lines[-1]
```

- [ ] **Step 2: 全链路测试 template_file**（使用 sample-template.docx + template runner）

- [ ] **Step 3: preflight 失败测试** — 无效 kb_id → exit 2 equivalent

- [ ] **Step 4: pytest PASS**

Run: `cd backend && ../.venv/bin/python -m pytest tests/integration/test_e2e_pipeline_flow.py -v`

- [ ] **Step 5: Commit** `test(e2e): add integration pipeline flow tests`

---

## Phase P6 — Live 验收与文档

### Task P6-1: Live smoke + README 片段

**Files:**
- Modify: `README.md`（增加 E2E 脚本用法 10 行）
- Modify: `docs/superpowers/specs/2026-06-14-e2e-import-retrieval-pipeline-design.md`（Status → Implemented 待 live 绿后）

- [ ] **Step 1: Live actual_bid smoke**

Run:
```bash
.venv/bin/python scripts/e2e_pipeline_test.py \
  --purpose actual_bid \
  --kb-id 8a27ac63-50c5-401f-998e-200649a94ca5 \
  --file backend/tests/fixtures/sample-actual-bid.docx \
  --keep-services
```
Expected: exit 0; `logs/e2e-*.jsonl` 含 `retrieval_dynamic`/`retrieval_smoke` ok

- [ ] **Step 2: Live template_file smoke**（同上 `--purpose template_file`）

- [ ] **Step 3: 验证 agent 排查** — 故意错误 kb-id，检查 jsonl 含 `preflight` failed + `http`

- [ ] **Step 4: README 追加**

```markdown
### E2E 验收脚本
\`\`\`bash
.venv/bin/python scripts/e2e_pipeline_test.py --purpose actual_bid --kb-id <KB_UUID> --file path/to.docx
\`\`\`
日志：`logs/e2e-<run_id>.jsonl`
```

- [ ] **Step 5: Commit** `docs: document e2e pipeline test script`

---

## Spec Coverage Checklist

| Spec 章节 | 任务 |
|-----------|------|
| D1 混合模式 | P4-2 integration_harness + P5 |
| D2 双 purpose | P2 + P3 + runner 分支 |
| D3 自动发布 | P1-2 step_auto_publish |
| D4 JSONL | P0-2 |
| D5 自动 start.sh | P4-2 CLI |
| D6 双重检索 | P1-2 |
| 5.4 runner fallback | P2-1, P3-1 fallback.py |
| 7.x JSONL schema | P0-2 |
| 10 teardown | P4-2 `--keep-services` |
| 11 验收命令 | P6-1 |

---

## P0 Checkpoint

完成 P0–P1 后应能：integration 模式 upload→confirm→（mock parse）→publish→retrieval 子集可跑。

## P1 Checkpoint（MVP）

完成 P2 + P4 后：integration actual_bid 全链路 exit 0。

## Production-ready

P0–P6 全绿 + Live smoke 两条 purpose 通过。
