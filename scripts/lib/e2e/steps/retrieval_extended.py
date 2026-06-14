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
            step="retrieval_bm25_only",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion=assertion,
            error={"type": "AssertionError", "message": "bm25-only returned no hits"},
        )
    return StepResult(
        step="retrieval_bm25_only",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp),
        assertion=assertion,
    )


def step_retrieval_category_filter(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.category_id or not ctx.published_object_ids:
        return StepResult(
            step="retrieval_category_filter",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            assertion={"name": "skip", "reason": "missing category or published KU"},
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
            step="retrieval_category_filter",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion=assertion,
            error={"type": "AssertionError", "message": "category filter missed published KU"},
        )
    return StepResult(
        step="retrieval_category_filter",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp),
        assertion=assertion,
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
            step="retrieval_trace",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion=assertion,
            error={"type": "AssertionError", "message": "missing trace_id"},
        )
    ctx.retrieval_trace_ids.append(str(trace_id))
    return StepResult(
        step="retrieval_trace",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={"retrieval_trace_ids": ctx.retrieval_trace_ids},
        http=http_meta("POST", path, resp),
        assertion=assertion,
    )
