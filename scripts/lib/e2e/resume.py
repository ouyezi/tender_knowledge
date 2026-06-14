from __future__ import annotations

from e2e.client import ApiClient
from e2e.types import FromStep, PipelineConfig, RunContext, StepResult
from e2e.steps.common import step_list_candidates


def load_import_context(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    import time

    from e2e.steps.common import _elapsed, _http_fail, _kb

    start = time.perf_counter()
    if not ctx.import_id:
        return StepResult(
            step="load_import_context",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing import_id"},
        )

    detail_path = f"{_kb(cfg)}/file-imports/{ctx.import_id}"
    detail_resp = api.request("GET", detail_path)
    if not detail_resp.ok:
        return _http_fail("load_import_context", start, "GET", detail_path, detail_resp)

    data = detail_resp.data()
    import_status = data.get("status") or ""
    patch: dict = {"import_id": ctx.import_id, "import_status": import_status}

    if cfg.purpose == "actual_bid":
        tasks_path = f"{_kb(cfg)}/actual-bid-parse/tasks"
        tasks_resp = api.request(
            "GET", tasks_path, params={"import_id": ctx.import_id, "page_size": 1}
        )
        if tasks_resp.ok:
            items = tasks_resp.data().get("items") or []
            if items:
                task = items[0]
                ctx.parse_task_id = str(task.get("parse_task_id") or ctx.parse_task_id or "")
                ctx.document_id = str(task.get("document_id") or ctx.document_id or "") or None
                ctx.bid_outline_id = str(task.get("bid_outline_id") or ctx.bid_outline_id or "") or None
                patch.update(
                    {
                        "parse_task_id": ctx.parse_task_id,
                        "document_id": ctx.document_id,
                        "bid_outline_id": ctx.bid_outline_id,
                        "parse_status": task.get("status"),
                    }
                )
    else:
        tasks_path = f"{_kb(cfg)}/template-parse/tasks"
        tasks_resp = api.request(
            "GET", tasks_path, params={"import_id": ctx.import_id, "page_size": 1}
        )
        if tasks_resp.ok:
            items = tasks_resp.data().get("items") or []
            if items:
                task = items[0]
                ctx.parse_task_id = str(task.get("parse_task_id") or ctx.parse_task_id or "")
                ctx.template_id = str(task.get("template_id") or ctx.template_id or "") or None
                patch.update(
                    {
                        "parse_task_id": ctx.parse_task_id,
                        "template_id": ctx.template_id,
                        "parse_status": task.get("status"),
                    }
                )

    return StepResult(
        step="load_import_context",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={k: v for k, v in patch.items() if v},
        http={"method": "GET", "path": detail_path, "status_code": detail_resp.status_code},
    )


def detect_from_step(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> FromStep:
    detail_path = f"/api/v1/kbs/{cfg.kb_id}/file-imports/{ctx.import_id}"
    detail_resp = api.request("GET", detail_path)
    if not detail_resp.ok:
        return "confirm"

    status = detail_resp.data().get("status") or ""
    if status in {"uploaded", "need_confirm"}:
        return "confirm"
    if status not in {"confirmed", "completed", "processing"}:
        return "confirm"

    load_import_context(api, cfg, ctx)

    if cfg.purpose == "actual_bid":
        if not ctx.parse_task_id:
            return "parse"
        task_resp = api.request(
            "GET",
            f"/api/v1/kbs/{cfg.kb_id}/actual-bid-parse/tasks/{ctx.parse_task_id}",
        )
        if not task_resp.ok:
            return "parse"
        parse_status = task_resp.data().get("status") or ""
        if parse_status in {"pending", "running", "failed"}:
            return "parse"
        if parse_status == "ready":
            return "parse"
    else:
        if not ctx.parse_task_id:
            return "parse"
        task_resp = api.request(
            "GET",
            f"/api/v1/kbs/{cfg.kb_id}/template-parse/tasks/{ctx.parse_task_id}",
        )
        if not task_resp.ok:
            return "parse"
        parse_status = task_resp.data().get("status") or ""
        if parse_status not in {"parse_ready", "confirmed"}:
            return "parse"
        if parse_status == "parse_ready":
            return "parse"

    list_result = step_list_candidates(api, cfg, ctx)
    if list_result.ok:
        return "publish"
    return "candidates"


def should_run(step: str, from_step: FromStep) -> bool:
    order = ["upload", "confirm", "parse", "candidates", "publish", "retrieval"]
    if from_step not in order:
        return True
    return order.index(step) >= order.index(from_step)
