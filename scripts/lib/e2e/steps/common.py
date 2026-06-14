from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from e2e.client import ApiClient, http_meta
from e2e.types import PipelineConfig, RunContext, StepResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _kb(cfg: PipelineConfig) -> str:
    return f"/api/v1/kbs/{cfg.kb_id}"


def _elapsed(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _http_fail(step: str, start: float, method: str, path: str, resp) -> StepResult:
    return StepResult(
        step=step,
        ok=False,
        duration_ms=_elapsed(start),
        http=http_meta(method, path, resp),
        error={"type": "HTTPError", "message": resp.raw_text[:500]},
    )


def step_preflight(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    health = api.request("GET", "/health")
    if not health.ok:
        return _http_fail("preflight", start, "GET", "/health", health)
    kb_path = f"{_kb(cfg)}"
    kb_resp = api.request("GET", kb_path)
    if not kb_resp.ok:
        return _http_fail("preflight", start, "GET", kb_path, kb_resp)
    return StepResult(step="preflight", ok=True, duration_ms=_elapsed(start))


def step_upload(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    path = f"{_kb(cfg)}/file-imports"
    form_data: dict[str, str] = {"duplicate_action": cfg.duplicate_action}
    if cfg.parent_import_id:
        form_data["parent_import_id"] = cfg.parent_import_id
    with cfg.file_path.open("rb") as handle:
        resp = api.request(
            "POST",
            path,
            files={"file": (cfg.file_path.name, handle, DOCX_MIME)},
            form_data=form_data,
        )
    if resp.status_code == 409:
        existing = (resp.json.get("error") or {}).get("details") or {}
        existing_ids = existing.get("existing_import_ids") or []
        hint = ""
        if existing_ids:
            hint = f" existing_import_ids={existing_ids}; retry with --duplicate-action new_version --parent-import-id {existing_ids[0]}"
        return StepResult(
            step="upload",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            error={
                "type": "DuplicateFile",
                "message": f"duplicate file.{hint}",
            },
        )
    if not resp.ok:
        return _http_fail("upload", start, "POST", path, resp)
    import_id = resp.data().get("import_id")
    if not import_id:
        return StepResult(
            step="upload",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            error={"type": "ValidationError", "message": "missing import_id"},
        )
    ctx.import_id = str(import_id)
    return StepResult(
        step="upload",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={"import_id": ctx.import_id},
        http=http_meta("POST", path, resp),
    )


def step_wait_need_confirm(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.import_id:
        return StepResult(
            step="wait_need_confirm",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing import_id"},
        )
    path = f"{_kb(cfg)}/file-imports/{ctx.import_id}"
    deadline = time.perf_counter() + cfg.poll_max_seconds
    last_status = ""

    while time.perf_counter() < deadline:
        resp = api.request("GET", path)
        if not resp.ok:
            return _http_fail("wait_need_confirm", start, "GET", path, resp)
        last_status = resp.data().get("status") or ""
        if last_status == "need_confirm":
            return StepResult(
                step="wait_need_confirm",
                ok=True,
                duration_ms=_elapsed(start),
                context_patch={"import_status": last_status},
                http=http_meta("GET", path, resp),
            )
        if last_status in {"confirmed", "completed", "processing"}:
            return StepResult(
                step="wait_need_confirm",
                ok=True,
                duration_ms=_elapsed(start),
                status="skipped",
                context_patch={"import_status": last_status},
                http=http_meta("GET", path, resp),
            )
        if last_status in {"failed", "ignored"}:
            return StepResult(
                step="wait_need_confirm",
                ok=False,
                duration_ms=_elapsed(start),
                http=http_meta("GET", path, resp),
                error={"type": "ImportError", "message": f"import status={last_status}"},
            )
        time.sleep(cfg.poll_interval_seconds)

    return StepResult(
        step="wait_need_confirm",
        ok=False,
        duration_ms=_elapsed(start),
        error={
            "type": "TimeoutError",
            "message": f"import stayed {last_status or 'unknown'} for {cfg.poll_max_seconds}s",
        },
    )


def step_confirm_import(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    detail_path = f"{_kb(cfg)}/file-imports/{ctx.import_id}"
    detail = api.request("GET", detail_path)
    if not detail.ok:
        return _http_fail("confirm_import", start, "GET", detail_path, detail)
    detail_data = detail.data()
    status = detail_data.get("status") or ""
    if status in {"confirmed", "completed", "processing"}:
        patch: dict[str, Any] = {"import_id": ctx.import_id, "import_status": status}
        if cfg.purpose == "actual_bid":
            tasks_resp = api.request(
                "GET",
                f"{_kb(cfg)}/actual-bid-parse/tasks",
                params={"import_id": ctx.import_id, "page_size": 1},
            )
            if tasks_resp.ok:
                items = tasks_resp.data().get("items") or []
                if items:
                    ctx.parse_task_id = str(items[0].get("parse_task_id") or "")
                    patch["parse_task_id"] = ctx.parse_task_id
                    task_detail = api.request(
                        "GET",
                        f"{_kb(cfg)}/actual-bid-parse/tasks/{ctx.parse_task_id}",
                    )
                    if task_detail.ok:
                        td = task_detail.data()
                        ctx.document_id = str(td.get("document_id") or "") or ctx.document_id
                        ctx.bid_outline_id = str(td.get("bid_outline_id") or "") or ctx.bid_outline_id
                        patch["document_id"] = ctx.document_id
                        patch["bid_outline_id"] = ctx.bid_outline_id
        else:
            tasks_resp = api.request(
                "GET",
                f"{_kb(cfg)}/template-parse/tasks",
                params={"import_id": ctx.import_id, "page_size": 1},
            )
            if tasks_resp.ok:
                items = tasks_resp.data().get("items") or []
                if items:
                    ctx.parse_task_id = str(items[0].get("parse_task_id") or "")
                    ctx.template_id = str(items[0].get("template_id") or "") or ctx.template_id
                    patch["parse_task_id"] = ctx.parse_task_id
        return StepResult(
            step="confirm_import",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            context_patch=patch,
            http=http_meta("GET", detail_path, detail),
        )
    version = detail_data.get("version")
    confirm_path = detail_path + "/confirm"
    resp = api.request(
        "POST",
        confirm_path,
        json_body={
            "expected_version": version,
            "file_purpose": cfg.purpose,
            "product_category_ids": [],
            "enter_parsing": True,
        },
    )
    if resp.status_code == 422 and "need_confirm" in resp.raw_text:
        return StepResult(
            step="confirm_import",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            http=http_meta("POST", confirm_path, resp),
            context_patch={"import_id": ctx.import_id},
        )
    if not resp.ok:
        return _http_fail("confirm_import", start, "POST", confirm_path, resp)
    data = resp.data()
    patch = {"import_id": ctx.import_id}
    if data.get("actual_bid_parse_task_id"):
        ctx.parse_task_id = str(data["actual_bid_parse_task_id"])
        patch["parse_task_id"] = ctx.parse_task_id
    return StepResult(
        step="confirm_import",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch=patch,
        http=http_meta("POST", confirm_path, resp),
    )


def step_load_import_context(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.import_id:
        return StepResult(
            step="load_import_context",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing import_id"},
        )
    patch: dict[str, Any] = {"import_id": ctx.import_id}
    if cfg.purpose == "actual_bid":
        tasks_resp = api.request(
            "GET",
            f"{_kb(cfg)}/actual-bid-parse/tasks",
            params={"import_id": ctx.import_id, "page_size": 1},
        )
        if not tasks_resp.ok:
            return _http_fail("load_import_context", start, "GET", f"{_kb(cfg)}/actual-bid-parse/tasks", tasks_resp)
        items = tasks_resp.data().get("items") or []
        if not items:
            return StepResult(
                step="load_import_context",
                ok=False,
                duration_ms=_elapsed(start),
                error={"type": "AssertionError", "message": "no parse task for import; run from --from-step parse or earlier"},
            )
        ctx.parse_task_id = str(items[0].get("parse_task_id") or "")
        patch["parse_task_id"] = ctx.parse_task_id
        task_resp = api.request("GET", f"{_kb(cfg)}/actual-bid-parse/tasks/{ctx.parse_task_id}")
        if not task_resp.ok:
            return _http_fail("load_import_context", start, "GET", f"{_kb(cfg)}/actual-bid-parse/tasks/{ctx.parse_task_id}", task_resp)
        td = task_resp.data()
        ctx.document_id = str(td.get("document_id") or "") or ctx.document_id
        ctx.bid_outline_id = str(td.get("bid_outline_id") or "") or ctx.bid_outline_id
        patch.update(
            {
                "document_id": ctx.document_id,
                "bid_outline_id": ctx.bid_outline_id,
                "parse_status": td.get("status"),
            }
        )
    else:
        tasks_resp = api.request(
            "GET",
            f"{_kb(cfg)}/template-parse/tasks",
            params={"import_id": ctx.import_id, "page_size": 1},
        )
        if not tasks_resp.ok:
            return _http_fail("load_import_context", start, "GET", f"{_kb(cfg)}/template-parse/tasks", tasks_resp)
        items = tasks_resp.data().get("items") or []
        if not items:
            return StepResult(
                step="load_import_context",
                ok=False,
                duration_ms=_elapsed(start),
                error={"type": "AssertionError", "message": "no template parse task for import"},
            )
        ctx.parse_task_id = str(items[0].get("parse_task_id") or "")
        ctx.template_id = str(items[0].get("template_id") or "") or ctx.template_id
        patch.update({"parse_task_id": ctx.parse_task_id, "template_id": ctx.template_id})
    return StepResult(
        step="load_import_context",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch=patch,
    )


def step_list_candidates(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    params: dict[str, Any] = {"status": "pending", "import_id": ctx.import_id, "page_size": 50}
    if cfg.purpose == "template_file":
        params["source_channel"] = "template"
    path = f"{_kb(cfg)}/candidates"
    resp = api.request("GET", path, params=params)
    if not resp.ok:
        return _http_fail("list_candidates", start, "GET", path, resp)
    items = resp.data().get("items") or []
    if not items:
        return StepResult(
            step="list_candidates",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("GET", path, resp),
            error={"type": "AssertionError", "message": "no pending candidates"},
        )
    ctx.candidate_ids = [item["candidate_id"] for item in items]
    return StepResult(
        step="list_candidates",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={"candidate_ids": ctx.candidate_ids},
        http=http_meta("GET", path, resp),
    )


def _resolve_taxonomy_and_category(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> None:
    if ctx.taxonomy_id and ctx.category_id:
        return
    tax_path = f"{_kb(cfg)}/chapter-taxonomies"
    tax_resp = api.request("GET", tax_path, params={"page_size": 1})
    if tax_resp.ok:
        items = tax_resp.data().get("items") or []
        if items:
            ctx.taxonomy_id = items[0]["taxonomy_id"]
    cat_path = f"{_kb(cfg)}/product-categories/tree"
    cat_resp = api.request("GET", cat_path)
    if cat_resp.ok:
        ctx.category_id = _first_category_id(cat_resp.data().get("items") or [])


def _first_category_id(nodes: list[dict]) -> str | None:
    for node in nodes:
        if node.get("category_id"):
            return str(node["category_id"])
        child = _first_category_id(node.get("children") or [])
        if child:
            return child
    return None


def step_auto_publish(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if cfg.auto_publish_count <= 0:
        return StepResult(
            step="auto_publish",
            ok=True,
            duration_ms=_elapsed(start),
            status="skipped",
            context_patch={"published_object_ids": [], "published_titles": []},
        )
    _resolve_taxonomy_and_category(api, cfg, ctx)
    if not ctx.candidate_ids:
        return StepResult(
            step="auto_publish",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "no candidates to publish"},
        )

    published_ids: list[str] = []
    published_titles: list[str] = []
    count = min(cfg.auto_publish_count, len(ctx.candidate_ids))

    for candidate_id in ctx.candidate_ids[:count]:
        confirm_path = f"{_kb(cfg)}/candidates/{candidate_id}/confirm"
        detail_path = f"{_kb(cfg)}/candidates/{candidate_id}"
        detail_resp = api.request("GET", detail_path)
        detail = detail_resp.data() if detail_resp.ok else {}

        body: dict[str, Any] = {
            "confirm_as": "ku",
            "knowledge_type": detail.get("suggested_knowledge_type") or "solution",
            "title": detail.get("title") or "E2E候选",
            "content": detail.get("content") or detail.get("content_preview") or "E2E自动发布正文",
            "searchable": True,
            "review_comment": "e2e auto publish",
        }
        if ctx.category_id:
            body["product_category_ids"] = [ctx.category_id]
        elif detail.get("suggested_product_category_ids"):
            body["product_category_ids"] = detail["suggested_product_category_ids"]
        if ctx.taxonomy_id:
            body["chapter_taxonomy_id"] = ctx.taxonomy_id
        elif detail.get("suggested_chapter_taxonomy_id"):
            body["chapter_taxonomy_id"] = detail["suggested_chapter_taxonomy_id"]

        resp = api.request("POST", confirm_path, json_body=body)
        if not resp.ok:
            return _http_fail("auto_publish", start, "POST", confirm_path, resp)

        data = resp.data()
        if data.get("status") != "published":
            return StepResult(
                step="auto_publish",
                ok=False,
                duration_ms=_elapsed(start),
                http=http_meta("POST", confirm_path, resp),
                error={"type": "AssertionError", "message": f"unexpected status {data.get('status')}"},
            )
        object_id = data.get("confirmed_object_id")
        if object_id:
            published_ids.append(str(object_id))
        title = detail.get("title") or data.get("title") or candidate_id
        published_titles.append(str(title))

    ctx.published_object_ids = published_ids
    ctx.published_titles = published_titles
    return StepResult(
        step="auto_publish",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={
            "published_object_ids": published_ids,
            "published_titles": published_titles,
        },
    )


def _extract_query(title: str) -> str:
    cleaned = "".join(ch for ch in title if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    if len(cleaned) >= 2:
        return cleaned[:8]
    return "技术方案"


def step_retrieval_dynamic(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    if not ctx.published_titles or not ctx.published_object_ids:
        return StepResult(
            step="retrieval_dynamic",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "no published objects"},
        )
    query = _extract_query(ctx.published_titles[0])
    ctx.query_used = query
    path = f"{_kb(cfg)}/retrieval/search"
    body = {
        "query": query,
        "intent": "knowledge_lookup",
        "retrieval_options": {"top_k": 10, "enable_bm25": True, "enable_vector": False},
        "return_options": {"include_trace": True},
    }
    if ctx.category_id:
        body["product_category_ids"] = [ctx.category_id]
    resp = api.request("POST", path, json_body=body)
    if not resp.ok:
        return _http_fail("retrieval_dynamic", start, "POST", path, resp)
    data = resp.data()
    items = data.get("items") or []
    hit_ids = {str(item.get("object_id")) for item in items}
    matched = any(obj_id in hit_ids for obj_id in ctx.published_object_ids)
    trace_id = data.get("trace_id")
    if trace_id:
        ctx.retrieval_trace_ids.append(str(trace_id))
    assertion = {
        "name": "retrieval_dynamic_hit",
        "expected": "published object_id in top_k",
        "actual": matched,
        "query": query,
    }
    if not matched:
        return StepResult(
            step="retrieval_dynamic",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion=assertion,
            error={"type": "AssertionError", "message": "published object not in hits"},
        )
    return StepResult(
        step="retrieval_dynamic",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch={"query_used": query},
        http=http_meta("POST", path, resp),
        assertion=assertion,
    )


def step_retrieval_smoke(api: ApiClient, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    start = time.perf_counter()
    path = f"{_kb(cfg)}/retrieval/search"
    body = {
        "query": "技术方案",
        "intent": "knowledge_lookup",
        "retrieval_options": {"top_k": 10, "enable_bm25": True, "enable_vector": False},
    }
    resp = api.request("POST", path, json_body=body)
    if not resp.ok:
        return _http_fail("retrieval_smoke", start, "POST", path, resp)
    total = resp.data().get("total", 0)
    assertion = {"name": "retrieval_smoke_nonempty", "expected": ">=1 hit", "actual": total}
    if total < 1:
        return StepResult(
            step="retrieval_smoke",
            ok=False,
            duration_ms=_elapsed(start),
            http=http_meta("POST", path, resp),
            assertion=assertion,
            error={"type": "AssertionError", "message": "smoke query returned no hits"},
        )
    return StepResult(
        step="retrieval_smoke",
        ok=True,
        duration_ms=_elapsed(start),
        http=http_meta("POST", path, resp),
        assertion=assertion,
    )


def step_candidate_ensure(db: Session, cfg: PipelineConfig, ctx: RunContext) -> StepResult:
    from e2e.taxonomy_backfill import backfill_taxonomy_for_document
    from src.services import candidate_generate_service

    start = time.perf_counter()
    if not ctx.document_id or not ctx.import_id:
        return StepResult(
            step="candidate_ensure",
            ok=False,
            duration_ms=_elapsed(start),
            error={"type": "AssertionError", "message": "missing document_id"},
        )
    kb_id = UUID(cfg.kb_id)
    import_id = UUID(ctx.import_id)
    document_id = UUID(ctx.document_id)
    parse_task_id = UUID(ctx.parse_task_id) if ctx.parse_task_id else None

    backfill_taxonomy_for_document(
        db,
        kb_id=kb_id,
        document_id=document_id,
    )
    created = candidate_generate_service.generate_for_document(
        db,
        kb_id=kb_id,
        import_id=import_id,
        document_id=document_id,
        parse_task_id=parse_task_id,
    )
    db.commit()

    patch: dict[str, Any] = {"created_candidates": len(created)}
    if created:
        taxonomy_id = created[0].suggested_chapter_taxonomy_id
        if taxonomy_id:
            ctx.taxonomy_id = str(taxonomy_id)
            patch["taxonomy_id"] = ctx.taxonomy_id
        if created[0].suggested_product_category_ids:
            ctx.category_id = str(created[0].suggested_product_category_ids[0])
            patch["category_id"] = ctx.category_id

    return StepResult(
        step="candidate_ensure",
        ok=True,
        duration_ms=_elapsed(start),
        context_patch=patch,
    )
