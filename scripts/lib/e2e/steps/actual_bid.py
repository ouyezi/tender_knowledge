from __future__ import annotations

import time
from typing import Callable

from e2e.client import ApiClient, http_meta
from e2e.types import PipelineConfig, RunContext, StepResult
from e2e.steps.common import _elapsed, _http_fail, _kb


def step_parse_trigger(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    if ctx.parse_task_id:
        return StepResult(step="parse_trigger", ok=True, duration_ms=0, status="skipped")
    start = time.perf_counter()
    path = f"{_kb(cfg)}/actual-bid-parse/trigger"
    resp = api.request("POST", path, json_body={"import_id": ctx.import_id})
    if not resp.ok:
        return _http_fail("parse_trigger", start, "POST", path, resp)
    ctx.parse_task_id = str(resp.data().get("parse_task_id") or "")
    if not ctx.parse_task_id:
        return StepResult(
            step="parse_trigger",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "ValidationError", "message": "missing parse_task_id"},
        )
    return StepResult(
        step="parse_trigger",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={"parse_task_id": ctx.parse_task_id},
        http=http_meta("POST", path, resp),
    )


def step_parse_poll(
    api: ApiClient,
    cfg: PipelineConfig,
    ctx: RunContext,
    *,
    run_fallback: Callable[[], bool] | None = None,
) -> StepResult:
    start = time.perf_counter()
    if not ctx.parse_task_id:
        return StepResult(
            step="parse_poll",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing parse_task_id"},
        )
    path = f"{_kb(cfg)}/actual-bid-parse/tasks/{ctx.parse_task_id}"
    deadline = time.perf_counter() + cfg.poll_max_seconds
    fallback_used = False

    while time.perf_counter() < deadline:
        resp = api.request("GET", path)
        if not resp.ok:
            return _http_fail("parse_poll", start, "GET", path, resp)
        data = resp.data()
        status = data.get("status")
        if status in {"ready", "confirmed"}:
            ctx.document_id = str(data.get("document_id") or "") or ctx.document_id
            ctx.bid_outline_id = str(data.get("bid_outline_id") or "") or ctx.bid_outline_id
            return StepResult(
                step="parse_poll",
                ok=True,
                duration_ms=_elapsed(start),
                context_patch={
                    "document_id": ctx.document_id,
                    "bid_outline_id": ctx.bid_outline_id,
                    "parse_status": status,
                },
                http=http_meta("GET", path, resp),
            )
        if status == "failed":
            return StepResult(
                step="parse_poll",
                ok=False,
                duration_ms=_elapsed(start),
                http=http_meta("GET", path, resp),
                error={"type": "ParseError", "message": "parse task failed"},
            )
        if run_fallback and not fallback_used and time.perf_counter() > start + cfg.poll_interval_seconds * 2:
            fallback_used = run_fallback()
        time.sleep(cfg.poll_interval_seconds)

    return StepResult(
        step="parse_poll",
        ok=False,
        duration_ms=_elapsed(start),
        error={"type": "TimeoutError", "message": f"parse poll exceeded {cfg.poll_max_seconds}s"},
    )


def step_parse_wizard_confirm(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.parse_task_id:
        return StepResult(
            step="parse_wizard_confirm",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing parse_task_id"},
        )
    task_path = f"{_kb(cfg)}/actual-bid-parse/tasks/{ctx.parse_task_id}"
    task_resp = api.request("GET", task_path)
    if task_resp.ok:
        task_data = task_resp.data()
        ctx.document_id = str(task_data.get("document_id") or "") or ctx.document_id
        ctx.bid_outline_id = str(task_data.get("bid_outline_id") or "") or ctx.bid_outline_id
        if task_data.get("status") == "confirmed":
            return StepResult(
                step="parse_wizard_confirm",
                ok=True,
                duration_ms=_elapsed(start),
                status="skipped",
                context_patch={
                    "document_id": ctx.document_id,
                    "bid_outline_id": ctx.bid_outline_id,
                    "parse_status": "confirmed",
                },
                http=http_meta("GET", task_path, task_resp),
            )
    if not ctx.bid_outline_id:
        return StepResult(
            step="parse_wizard_confirm",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing bid_outline_id"},
        )
    nodes_path = f"{_kb(cfg)}/bid-outlines/{ctx.bid_outline_id}/nodes"
    nodes_resp = api.request("GET", nodes_path)
    if not nodes_resp.ok:
        return _http_fail("parse_wizard_confirm", start, "GET", nodes_path, nodes_resp)
    outline_nodes = [
        {
            "outline_node_id": node["outline_node_id"],
            "parent_id": node.get("parent_id"),
            "title": node["title"],
            "level": node["level"],
            "sort_order": node.get("sort_order", 0),
            "chapter_taxonomy_id": node.get("chapter_taxonomy_id"),
            "product_category_ids": node.get("product_category_ids", []),
            "needs_manual_review": node.get("needs_manual_review", False),
        }
        for node in nodes_resp.data().get("nodes") or []
    ]
    confirm_path = f"{_kb(cfg)}/actual-bid-parse/tasks/{ctx.parse_task_id}/confirm"
    resp = api.request(
        "POST",
        confirm_path,
        json_body={
            "document": {
                "bid_project_name": "E2E测试项目",
                "bid_customer_name": "E2E测试客户",
                "product_category_ids": [],
            },
            "outline_nodes": outline_nodes,
        },
    )
    if not resp.ok:
        return _http_fail("parse_wizard_confirm", start, "POST", confirm_path, resp)
    if resp.data().get("status") not in {"confirmed", "ready"}:
        return StepResult(
            step="parse_wizard_confirm",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", confirm_path, resp),
            error={"type": "AssertionError", "message": f"unexpected status {resp.data().get('status')}"},
        )
    return StepResult(
        step="parse_wizard_confirm",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("POST", confirm_path, resp),
    )
