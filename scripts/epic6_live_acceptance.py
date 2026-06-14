#!/usr/bin/env python3
"""Epic 6 live acceptance with real Qwen LLM."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from uuid import UUID

BASE = "http://127.0.0.1:8000"
KB_ID = "8a27ac63-50c5-401f-998e-200649a94ca5"
OP = "admin"
HEADERS = {"Content-Type": "application/json", "X-Operator-Id": OP}


def req(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
            return {"status": resp.status, **payload}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return {"status": exc.code, **payload}


def main() -> int:
    print("=== Epic 6 Live Acceptance ===")
    health = req("GET", "/health")
    if health.get("status") != "ok" and health.get("status") != 200:
        print("FAIL: health", health)
        return 1
    print("OK: health")

    from src.config import settings

    print(f"LLM: {settings.resolved_llm_model} @ {settings.resolved_llm_base_url}")

    cats = req("GET", f"/api/v1/kbs/{KB_ID}/product-categories/tree")
    if cats.get("status") != 200:
        print("FAIL: categories", cats)
        return 1

    def first_cat_id(nodes: list) -> str | None:
        for node in nodes:
            if node.get("category_id"):
                return node["category_id"]
            child = first_cat_id(node.get("children") or [])
            if child:
                return child
        return None

    category_id = first_cat_id(cats.get("data", {}).get("items", []))
    if not category_id:
        print("WARN: no product category; using empty list")
        category_id = None

    ctx = req(
        "POST",
        f"/api/v1/kbs/{KB_ID}/tender-requirements",
        {
            "title": "Epic6 本地验收-LLM",
            "outline_nodes": [{"title": "1.1 总体架构", "level": 2, "sort_order": 1}],
            "score_points": [{"node_ref": "1.1 总体架构", "text": "架构清晰、可扩展"}],
            "rejection_clauses": ["未提供资质证明废标"],
            "format_requirements": ["目录须三级编号"],
            "response_clauses": ["须逐条响应技术规格书"],
        },
    )
    if ctx.get("status") != 200:
        print("FAIL: create tender context", json.dumps(ctx, ensure_ascii=False, indent=2))
        return 1
    ctx_id = ctx["data"]["requirement_context_id"]
    print(f"OK: tender context {ctx_id}")

    sug_body = {
        "requirement_context_id": ctx_id,
        "product_category_ids": [category_id] if category_id else [],
        "outline_nodes": [{"title": "1.1 总体架构", "level": 2, "sort_order": 1}],
        "tender_requirement_context": {
            "score_points": ["架构清晰、可扩展"],
            "rejection_clauses": ["未提供资质证明废标"],
        },
        "return_options": {"include_trace": True, "include_conflict_flags": True},
    }
    sug = req("POST", f"/api/v1/kbs/{KB_ID}/module-suggestions", sug_body)
    if sug.get("status") != 200:
        print("FAIL: module suggestion", json.dumps(sug, ensure_ascii=False, indent=2))
        return 1
    suggestion_id = sug["data"]["module_suggestions"][0]["suggestion_id"]
    print(f"OK: suggestion {suggestion_id}")

    adopt = req(
        "PATCH",
        f"/api/v1/kbs/{KB_ID}/module-suggestions/{suggestion_id}/adoption",
        {"status": "adopted", "adoption_reason": "本地验收采纳"},
    )
    if adopt.get("status") != 200:
        print("FAIL: adoption", adopt)
        return 1
    print("OK: adopted")

    draft_body = {
        "requirement_context_id": ctx_id,
        "suggestion_id": suggestion_id,
        "target_outline_node": {"title": "1.1 总体架构", "level": 2, "sort_order": 1},
        "product_category_ids": [category_id] if category_id else [],
        "variable_values": {"project_name": "本地验收项目", "customer_name": "测试客户"},
        "manual_asset_compliance": [],
    }
    draft = req("POST", f"/api/v1/kbs/{KB_ID}/generation/drafts", draft_body)
    if draft.get("status") not in (200, 202):
        print("FAIL: create draft", json.dumps(draft, ensure_ascii=False, indent=2))
        return 1
    task_id = draft["data"]["task_id"]
    print(f"OK: generation task {task_id} — polling (live LLM)...")

    for i in range(60):
        time.sleep(3)
        task = req("GET", f"/api/v1/kbs/{KB_ID}/generation/tasks/{task_id}")
        status = task.get("data", {}).get("status")
        print(f"  poll {i+1}: {status}")
        if status == "completed":
            draft_id = task["data"]["draft_id"]
            snapshot_id = task["data"]["snapshot_id"]
            break
        if status == "failed":
            print("FAIL: task failed", json.dumps(task, ensure_ascii=False, indent=2))
            return 1
    else:
        print("FAIL: task timeout")
        return 1

    draft_detail = req("GET", f"/api/v1/kbs/{KB_ID}/generation/drafts/{draft_id}")
    snap = req("GET", f"/api/v1/kbs/{KB_ID}/generation/snapshots/{snapshot_id}")
    paragraphs = draft_detail.get("data", {}).get("paragraphs", [])
    citations = sum(len(p.get("citations") or []) for p in paragraphs)
    print(f"OK: draft {draft_id} paragraphs={len(paragraphs)} citations={citations}")
    print(f"OK: snapshot prompt_version={snap.get('data', {}).get('prompt_version')}")
    if paragraphs:
        print("--- first paragraph preview ---")
        print(paragraphs[0].get("text", "")[:300])
    if citations == 0:
        print("WARN: no citations on draft")
        return 1

    accept = req("POST", f"/api/v1/kbs/{KB_ID}/generation/drafts/{draft_id}/accept")
    if accept.get("data", {}).get("outcome_status") != "accepted":
        print("FAIL: accept", accept)
        return 1
    print("OK: accepted draft")
    print("=== Epic 6 Live Acceptance PASSED ===")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, "/Users/tongqianni/xlab/tender_knowledge/backend")
    raise SystemExit(main())
