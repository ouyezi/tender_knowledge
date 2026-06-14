from __future__ import annotations

import time
from typing import Any

from e2e.client import ApiClient, http_meta
from e2e.steps.common import _elapsed, _http_fail, _kb, _resolve_taxonomy_and_category
from e2e.types import PipelineConfig, RunContext, StepResult


def should_skip_merge(candidate_ids: list[str]) -> bool:
    return len(candidate_ids) < 4


def pick_ignore_candidate(candidate_ids: list[str], published_id: str | None) -> str | None:
    for candidate_id in reversed(candidate_ids):
        if candidate_id != published_id:
            return candidate_id
    return None


def _candidate_detail(api: ApiClient, cfg: PipelineConfig, candidate_id: str) -> tuple[dict[str, Any], str | None]:
    path = f"{_kb(cfg)}/candidates/{candidate_id}"
    resp = api.request("GET", path)
    if not resp.ok:
        return {}, path
    return resp.data(), None


def step_wb_pending_exists(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    path = f"{_kb(cfg)}/candidates"
    resp = api.request("GET", path, params={"status": "pending", "page_size": 50})
    if not resp.ok:
        return _http_fail("wb_pending_exists", start, "GET", path, resp)
    data = resp.data()
    items = data.get("items") or []
    total = int(data.get("total") or len(items))
    if total < 3:
        return StepResult(
            step="wb_pending_exists",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("GET", path, resp),
            assertion={"name": "pending_total", "expected": ">=3", "actual": total},
            error={"type": "AssertionError", "message": f"pending total too small: {total}"},
        )
    ctx.candidate_ids = [str(item.get("candidate_id")) for item in items if item.get("candidate_id")]
    return StepResult(
        step="wb_pending_exists",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("GET", path, resp),
        assertion={"name": "pending_total", "expected": ">=3", "actual": total},
        context_patch={"candidate_ids": ctx.candidate_ids},
    )


def step_wb_filter_by_import(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.import_id:
        return StepResult(
            step="wb_filter_by_import",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing import_id"},
        )
    _resolve_taxonomy_and_category(api, cfg, ctx)
    if not ctx.taxonomy_id:
        return StepResult(
            step="wb_filter_by_import",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing taxonomy_id"},
        )
    path = f"{_kb(cfg)}/candidates"
    params = {
        "status": "pending",
        "import_id": ctx.import_id,
        "chapter_taxonomy_id": ctx.taxonomy_id,
        "page_size": 50,
    }
    resp = api.request("GET", path, params=params)
    if not resp.ok:
        return _http_fail("wb_filter_by_import", start, "GET", path, resp)
    items = resp.data().get("items") or []
    if len(items) < 1:
        return StepResult(
            step="wb_filter_by_import",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("GET", path, resp),
            assertion={"name": "filtered_count", "expected": ">=1", "actual": 0},
            error={"type": "AssertionError", "message": "no filtered pending candidates"},
        )
    ids = [str(item.get("candidate_id")) for item in items if item.get("candidate_id")]
    ctx.candidate_ids = ids
    return StepResult(
        step="wb_filter_by_import",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("GET", path, resp),
        assertion={"name": "filtered_count", "expected": ">=1", "actual": len(items)},
        context_patch={"candidate_ids": ctx.candidate_ids},
    )


def step_wb_edit_candidate(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.candidate_ids:
        return StepResult(
            step="wb_edit_candidate",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing candidate_ids"},
        )
    candidate_id = ctx.candidate_ids[0]
    path = f"{_kb(cfg)}/candidates/{candidate_id}"
    resp = api.request(
        "PATCH",
        path,
        json_body={
            "title": "dingxin-workbench-revised-title",
            "summary": "dingxin quickstart revised summary",
        },
    )
    if not resp.ok:
        return _http_fail("wb_edit_candidate", start, "PATCH", path, resp)
    status = str(resp.data().get("status") or "")
    if status != "pending":
        return StepResult(
            step="wb_edit_candidate",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("PATCH", path, resp),
            assertion={"name": "status_after_patch", "expected": "pending", "actual": status},
            error={"type": "AssertionError", "message": f"unexpected status after patch: {status}"},
        )
    return StepResult(
        step="wb_edit_candidate",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("PATCH", path, resp),
        assertion={"name": "status_after_patch", "expected": "pending", "actual": status},
    )


def step_wb_publish_single(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.candidate_ids:
        return StepResult(
            step="wb_publish_single",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing candidate_ids"},
        )
    _resolve_taxonomy_and_category(api, cfg, ctx)
    candidate_id = ctx.candidate_ids[0]
    detail, failed_path = _candidate_detail(api, cfg, candidate_id)
    if failed_path:
        detail = {}
    body: dict[str, Any] = {
        "confirm_as": "ku",
        "knowledge_type": detail.get("suggested_knowledge_type") or "solution",
        "searchable": True,
        "review_comment": "dingxin workbench single publish",
    }
    if ctx.category_id:
        body["product_category_ids"] = [ctx.category_id]
    elif detail.get("suggested_product_category_ids"):
        body["product_category_ids"] = detail["suggested_product_category_ids"]
    if ctx.taxonomy_id:
        body["chapter_taxonomy_id"] = ctx.taxonomy_id
    elif detail.get("suggested_chapter_taxonomy_id"):
        body["chapter_taxonomy_id"] = detail["suggested_chapter_taxonomy_id"]
    path = f"{_kb(cfg)}/candidates/{candidate_id}/confirm"
    resp = api.request("POST", path, json_body=body)
    if not resp.ok:
        return _http_fail("wb_publish_single", start, "POST", path, resp)
    data = resp.data()
    status = str(data.get("status") or "")
    object_id = data.get("confirmed_object_id")
    if status != "published" or not object_id:
        return StepResult(
            step="wb_publish_single",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion={"name": "publish_status", "expected": "published+object", "actual": {"status": status, "object_id": object_id}},
            error={"type": "AssertionError", "message": "single publish failed"},
        )
    title = str(detail.get("title") or data.get("title") or candidate_id)
    ctx.published_object_ids.append(str(object_id))
    ctx.published_titles.append(title)
    return StepResult(
        step="wb_publish_single",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp),
        context_patch={"published_object_ids": [str(object_id)], "published_titles": [title]},
    )


def step_wb_ignore_candidate(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    published_id = ctx.candidate_ids[0] if ctx.candidate_ids else None
    ignore_id = pick_ignore_candidate(ctx.candidate_ids, published_id)
    if not ignore_id:
        return StepResult(
            step="wb_ignore_candidate",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            assertion={"name": "ignore_candidate", "reason": "no ignore candidate"},
        )
    path = f"{_kb(cfg)}/candidates/{ignore_id}/confirm"
    resp = api.request(
        "POST",
        path,
        json_body={"confirm_as": "ignore", "review_comment": "dingxin low value ignore"},
    )
    if not resp.ok:
        return _http_fail("wb_ignore_candidate", start, "POST", path, resp)
    status = str(resp.data().get("status") or "")
    if status != "rejected":
        return StepResult(
            step="wb_ignore_candidate",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion={"name": "ignore_status", "expected": "rejected", "actual": status},
            error={"type": "AssertionError", "message": f"ignore unexpected status: {status}"},
        )
    return StepResult(
        step="wb_ignore_candidate",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp),
        assertion={"name": "ignore_status", "expected": "rejected", "actual": status},
    )


def step_wb_merge_candidates(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if should_skip_merge(ctx.candidate_ids):
        return StepResult(
            step="wb_merge_candidates",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            assertion={"name": "merge_skip", "reason": "candidate count < 4"},
        )
    target_id = ctx.candidate_ids[1]
    source_id = ctx.candidate_ids[3]
    if target_id == source_id:
        return StepResult(
            step="wb_merge_candidates",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            assertion={"name": "merge_skip", "reason": "target equals source"},
        )
    path = f"{_kb(cfg)}/candidates/merge"
    resp = api.request(
        "POST",
        path,
        json_body={
            "target_candidate_id": target_id,
            "source_candidate_ids": [source_id],
            "review_comment": "dingxin duplicate merge",
        },
    )
    if not resp.ok:
        return _http_fail("wb_merge_candidates", start, "POST", path, resp)
    merged_count = int(resp.data().get("merged_count") or 0)
    if merged_count != 1:
        return StepResult(
            step="wb_merge_candidates",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion={"name": "merged_count", "expected": 1, "actual": merged_count},
            error={"type": "AssertionError", "message": f"unexpected merged_count: {merged_count}"},
        )
    return StepResult(
        step="wb_merge_candidates",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp),
        assertion={"name": "merged_count", "expected": 1, "actual": merged_count},
    )


def step_wb_batch_confirm(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.import_id:
        return StepResult(
            step="wb_batch_confirm",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing import_id"},
        )
    _resolve_taxonomy_and_category(api, cfg, ctx)
    list_path = f"{_kb(cfg)}/candidates"
    list_resp = api.request(
        "GET",
        list_path,
        params={"status": "pending", "import_id": ctx.import_id, "page_size": 5},
    )
    if not list_resp.ok:
        return _http_fail("wb_batch_confirm", start, "GET", list_path, list_resp)
    items = list_resp.data().get("items") or []
    picked = items[:2]
    if len(picked) < 2:
        return StepResult(
            step="wb_batch_confirm",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            assertion={"name": "batch_skip", "reason": "pending candidates < 2"},
        )
    first_id = str(picked[0].get("candidate_id"))
    second_id = str(picked[1].get("candidate_id"))
    batch_items: list[dict[str, Any]] = [
        {
            "candidate_id": first_id,
            "confirm_as": "ku",
            "knowledge_type": "solution",
            "product_category_ids": [ctx.category_id] if ctx.category_id else [],
            "chapter_taxonomy_id": ctx.taxonomy_id,
        },
        {"candidate_id": second_id, "confirm_as": "ignore"},
    ]
    path = f"{_kb(cfg)}/candidates/batch/confirm"
    resp = api.request(
        "POST",
        path,
        json_body={"items": batch_items, "batch_comment": "dingxin quickstart batch"},
    )
    if not resp.ok:
        return _http_fail("wb_batch_confirm", start, "POST", path, resp)
    data = resp.data()
    batch_id = str(data.get("batch_id") or "")
    processed = int(data.get("succeeded") or 0) + int(data.get("failed") or 0)
    if not batch_id or processed < 1:
        return StepResult(
            step="wb_batch_confirm",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion={"name": "batch_processed", "expected": "batch_id and >=1", "actual": {"batch_id": batch_id, "processed": processed}},
            error={"type": "AssertionError", "message": "batch confirm result invalid"},
        )
    return StepResult(
        step="wb_batch_confirm",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp),
        assertion={"name": "batch_processed", "expected": "batch_id and >=1", "actual": {"batch_id": batch_id, "processed": processed}},
    )


def step_wb_audit_log(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.candidate_ids:
        return StepResult(
            step="wb_audit_log",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing candidate_ids"},
        )
    candidate_id = ctx.candidate_ids[0]
    path = f"{_kb(cfg)}/candidate-audit-logs"
    resp = api.request("GET", path, params={"candidate_id": candidate_id})
    if not resp.ok:
        return _http_fail("wb_audit_log", start, "GET", path, resp)
    actions = [str(item.get("action")) for item in (resp.data().get("items") or []) if item.get("action")]
    has_publish = "publish" in actions
    if not has_publish:
        return StepResult(
            step="wb_audit_log",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("GET", path, resp),
            assertion={"name": "audit_publish", "expected": "contains publish", "actual": actions},
            error={"type": "AssertionError", "message": "audit log missing publish"},
        )
    return StepResult(
        step="wb_audit_log",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("GET", path, resp),
        assertion={"name": "audit_publish", "expected": "contains publish", "actual": actions},
    )


def step_wb_retry_publish(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.import_id:
        return StepResult(
            step="wb_retry_publish",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing import_id"},
        )
    _resolve_taxonomy_and_category(api, cfg, ctx)
    list_path = f"{_kb(cfg)}/candidates"
    list_resp = api.request(
        "GET",
        list_path,
        params={"status": "pending", "import_id": ctx.import_id, "page_size": 1},
    )
    if not list_resp.ok:
        return _http_fail("wb_retry_publish", start, "GET", list_path, list_resp)
    items = list_resp.data().get("items") or []
    if not items:
        return StepResult(
            step="wb_retry_publish",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            assertion={"name": "retry_skip", "reason": "no pending candidate"},
        )
    candidate_id = str(items[0].get("candidate_id"))
    confirm_path = f"{_kb(cfg)}/candidates/{candidate_id}/confirm"
    # Intentionally incomplete KU payload → validation/publish failure + publish_failed audit
    # (aligned with backend/tests/integration/test_epic4_quickstart_flow.py scenario 8)
    fail_body: dict[str, Any] = {"confirm_as": "ku"}
    if ctx.taxonomy_id:
        fail_body["chapter_taxonomy_id"] = ctx.taxonomy_id
    confirm_resp = api.request("POST", confirm_path, json_body=fail_body)
    if confirm_resp.status_code not in {422, 200}:
        return _http_fail("wb_retry_publish", start, "POST", confirm_path, confirm_resp)
    retry_path = f"{_kb(cfg)}/candidates/{candidate_id}/retry-publish"
    retry_body: dict[str, Any] = {
        "confirm_as": "ku",
        "knowledge_type": "solution",
        "content": "zhongtie workbench retry publish body",
    }
    if ctx.category_id:
        retry_body["product_category_ids"] = [ctx.category_id]
    if ctx.taxonomy_id:
        retry_body["chapter_taxonomy_id"] = ctx.taxonomy_id
    retry_resp = api.request("POST", retry_path, json_body=retry_body)
    if not retry_resp.ok:
        return _http_fail("wb_retry_publish", start, "POST", retry_path, retry_resp)
    retry_status = str(retry_resp.data().get("status") or "")
    if retry_status != "published":
        return StepResult(
            step="wb_retry_publish",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", retry_path, retry_resp),
            assertion={"name": "retry_status", "expected": "published", "actual": retry_status},
            error={"type": "AssertionError", "message": f"unexpected retry status: {retry_status}"},
        )
    audit_path = f"{_kb(cfg)}/candidate-audit-logs"
    audit_resp = api.request("GET", audit_path, params={"candidate_id": candidate_id})
    if not audit_resp.ok:
        return _http_fail("wb_retry_publish", start, "GET", audit_path, audit_resp)
    actions = [str(item.get("action")) for item in (audit_resp.data().get("items") or []) if item.get("action")]
    if "publish_failed" not in actions:
        return StepResult(
            step="wb_retry_publish",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("GET", audit_path, audit_resp),
            assertion={"name": "retry_audit", "expected": "contains publish_failed", "actual": actions},
            error={"type": "AssertionError", "message": "audit missing publish_failed"},
        )
    return StepResult(
        step="wb_retry_publish",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("GET", audit_path, audit_resp),
        assertion={"name": "retry_audit", "expected": "contains publish_failed", "actual": actions},
    )


def step_wb_retrieval_isolation(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.import_id:
        return StepResult(
            step="wb_retrieval_isolation",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing import_id"},
        )
    pending_path = f"{_kb(cfg)}/candidates"
    pending_resp = api.request(
        "GET",
        pending_path,
        params={"status": "pending", "import_id": ctx.import_id, "page_size": 1},
    )
    if not pending_resp.ok:
        return _http_fail("wb_retrieval_isolation", start, "GET", pending_path, pending_resp)
    pending_items = pending_resp.data().get("items") or []
    if not pending_items:
        return StepResult(
            step="wb_retrieval_isolation",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            assertion={"name": "isolation_skip", "reason": "no pending sample"},
        )
    sample_id = str(pending_items[0].get("candidate_id") or "")
    sample_norm = sample_id.replace("doc_", "")
    ku_path = f"{_kb(cfg)}/knowledge-units"
    ku_resp = api.request("GET", ku_path, params={"status": "published", "page_size": 100})
    if not ku_resp.ok:
        return _http_fail("wb_retrieval_isolation", start, "GET", ku_path, ku_resp)
    ku_items = ku_resp.data().get("items") or []
    leak_count = len([item for item in ku_items if str(item.get("candidate_id") or "") == sample_norm])
    if leak_count != 0:
        return StepResult(
            step="wb_retrieval_isolation",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("GET", ku_path, ku_resp),
            assertion={"name": "pending_not_in_published", "expected": 0, "actual": leak_count},
            error={"type": "AssertionError", "message": f"pending candidate leaked to published list: {leak_count}"},
        )
    return StepResult(
        step="wb_retrieval_isolation",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("GET", ku_path, ku_resp),
        assertion={"name": "pending_not_in_published", "expected": 0, "actual": leak_count},
    )


WORKBENCH_STEPS = [
    step_wb_pending_exists,
    step_wb_filter_by_import,
    step_wb_edit_candidate,
    step_wb_publish_single,
    step_wb_ignore_candidate,
    step_wb_merge_candidates,
    step_wb_batch_confirm,
    step_wb_audit_log,
    step_wb_retry_publish,
    step_wb_retrieval_isolation,
]
