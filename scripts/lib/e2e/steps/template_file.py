from __future__ import annotations

import time
from typing import Callable

from e2e.client import ApiClient, http_meta
from e2e.types import PipelineConfig, RunContext, StepResult
from e2e.steps.common import _elapsed, _http_fail, _kb


def step_template_parse_trigger(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    path = f"{_kb(cfg)}/template-parse/trigger"
    resp = api.request("POST", path, json_body={"import_id": ctx.import_id})
    if not resp.ok:
        return _http_fail("template_parse_trigger", start, "POST", path, resp)
    data = resp.data()
    ctx.parse_task_id = str(data.get("parse_task_id") or ctx.parse_task_id or "")
    if data.get("template_id"):
        ctx.template_id = str(data["template_id"])
    if not ctx.parse_task_id:
        return StepResult(
            step="template_parse_trigger",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "ValidationError", "message": "missing parse_task_id"},
        )
    return StepResult(
        step="template_parse_trigger",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={"parse_task_id": ctx.parse_task_id, "template_id": ctx.template_id},
        http=http_meta("POST", path, resp),
    )


def step_template_parse_poll(
    api: ApiClient,
    cfg: PipelineConfig,
    ctx: RunContext,
    *,
    run_fallback: Callable[[], bool] | None = None,
) -> StepResult:
    start = time.perf_counter()
    if not ctx.parse_task_id:
        trigger = step_template_parse_trigger(api, cfg, ctx)
        if not trigger.ok:
            return StepResult(
                step="template_parse_poll",
                ok=False,
                duration_ms=_elapsed(start),
                error=trigger.error,
            )

    path = f"{_kb(cfg)}/template-parse/tasks/{ctx.parse_task_id}"
    deadline = time.perf_counter() + cfg.poll_max_seconds
    fallback_used = False

    while time.perf_counter() < deadline:
        resp = api.request("GET", path)
        if not resp.ok:
            return _http_fail("template_parse_poll", start, "GET", path, resp)
        data = resp.data()
        status = data.get("status")
        if status == "parse_ready":
            ctx.template_id = str(data.get("template_id") or ctx.template_id or "")
            return StepResult(
                step="template_parse_poll",
                ok=True,
                duration_ms=_elapsed(start),
                context_patch={"template_id": ctx.template_id, "parse_status": status},
                http=http_meta("GET", path, resp),
            )
        if status == "confirmed":
            ctx.template_id = str(data.get("template_id") or ctx.template_id or "")
            return StepResult(step="template_parse_poll", ok=True, duration_ms=_elapsed(start), status="skipped")
        if status == "failed":
            return StepResult(
                step="template_parse_poll",
                ok=False,
                duration_ms=_elapsed(start),
                http=http_meta("GET", path, resp),
                error={"type": "ParseError", "message": "template parse failed"},
            )
        if run_fallback and not fallback_used and time.perf_counter() > start + cfg.poll_interval_seconds * 2:
            fallback_used = run_fallback()
        time.sleep(cfg.poll_interval_seconds)

    return StepResult(
        step="template_parse_poll",
        ok=False,
        duration_ms=_elapsed(start),
        error={"type": "TimeoutError", "message": f"template poll exceeded {cfg.poll_max_seconds}s"},
    )


def step_template_parse_confirm(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.parse_task_id:
        return StepResult(
            step="template_parse_confirm",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing parse_task_id"},
        )
    suggestion_path = f"{_kb(cfg)}/template-parse/tasks/{ctx.parse_task_id}/suggestion"
    suggestion_resp = api.request("GET", suggestion_path)
    if not suggestion_resp.ok:
        return _http_fail("template_parse_confirm", start, "GET", suggestion_path, suggestion_resp)
    suggestion = suggestion_resp.data()
    chapters = []
    for node in suggestion.get("suggested_chapter_tree") or []:
        chapters.append(
            {
                "temp_id": node.get("temp_id"),
                "parent_temp_id": node.get("parent_temp_id"),
                "title": node.get("title") or "章节",
                "level": node.get("level") or 1,
                "sort_order": node.get("sort_order") or 0,
                "chapter_taxonomy_id": node.get("chapter_taxonomy_id"),
                "product_category_ids": node.get("product_category_ids") or [],
                "required": node.get("required", False),
                "is_fixed_section": node.get("is_fixed_section", False),
                "ignored": node.get("ignored", False),
            }
        )
    materials = []
    for material in suggestion.get("suggested_materials") or []:
        materials.append(
            {
                "temp_id": material.get("temp_id"),
                "chapter_temp_id": material.get("chapter_temp_id"),
                "material_type": material.get("material_type") or "fixed_paragraph",
                "title": material.get("title"),
                "summary": material.get("summary"),
                "content": material.get("content"),
                "product_category_ids": material.get("product_category_ids") or [],
                "extract_as_candidate": material.get("extract_as_candidate", False),
                "ignored": material.get("ignored", False),
            }
        )
    candidate_actions = []
    for candidate in suggestion.get("suggested_candidates") or []:
        candidate_actions.append(
            {
                "temp_id": candidate.get("temp_id"),
                "candidate_type": candidate.get("candidate_type") or "ku",
                "accepted": True,
                "product_category_ids": candidate.get("product_category_ids") or [],
                "chapter_taxonomy_id": candidate.get("chapter_taxonomy_id"),
                "knowledge_type": candidate.get("knowledge_type") or "solution",
            }
        )
    if chapters and not candidate_actions:
        candidate_actions = [{"temp_id": "c-auto", "candidate_type": "ku", "accepted": True}]

    confirm_path = f"{_kb(cfg)}/template-parse/tasks/{ctx.parse_task_id}/confirm"
    resp = api.request(
        "POST",
        confirm_path,
        json_body={
            "template_library_id": None,
            "template_name": suggestion.get("suggested_library_name") or cfg.file_path.stem,
            "template_type": "technical_bid",
            "product_category_ids": suggestion.get("suggested_product_category_ids") or [],
            "chapters": chapters or [
                {
                    "temp_id": "n1",
                    "parent_temp_id": None,
                    "title": "默认章节",
                    "level": 1,
                    "sort_order": 0,
                    "product_category_ids": [],
                    "required": True,
                    "is_fixed_section": False,
                    "ignored": False,
                }
            ],
            "materials": materials,
            "candidate_actions": candidate_actions,
        },
    )
    if not resp.ok:
        return _http_fail("template_parse_confirm", start, "POST", confirm_path, resp)
    data = resp.data()
    if data.get("template_id"):
        ctx.template_id = str(data["template_id"])
    if data.get("status") != "confirmed":
        return StepResult(
            step="template_parse_confirm",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", confirm_path, resp),
            error={"type": "AssertionError", "message": f"unexpected status {data.get('status')}"},
        )
    return StepResult(
        step="template_parse_confirm",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={"template_id": ctx.template_id},
        http=http_meta("POST", confirm_path, resp),
    )
