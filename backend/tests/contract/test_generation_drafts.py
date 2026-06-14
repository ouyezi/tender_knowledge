def test_create_draft_llm_unavailable_returns_503(client, epic6_generation_seed, monkeypatch):
    monkeypatch.setattr("src.api.routes.generation.is_llm_available", lambda: False)

    resp = client.post(
        f"/api/v1/kbs/{epic6_generation_seed['kb_id']}/generation/drafts",
        json={
            "requirement_context_id": epic6_generation_seed["requirement_context_id"],
            "suggestion_id": epic6_generation_seed["suggestion_id"],
            "target_outline_node": {
                "title": "技术方案",
                "level": 1,
                "sort_order": 0,
            },
            "variable_values": {},
        },
        headers={"X-Operator-Id": "tester"},
    )

    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "LLM_UNAVAILABLE"


def test_create_generation_draft_returns_task_id(client, epic6_generation_seed, monkeypatch):
    monkeypatch.setattr("src.api.routes.generation.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "src.api.routes.generation.run_generation_task_in_new_session",
        lambda _task_id: None,
    )

    resp = client.post(
        f"/api/v1/kbs/{epic6_generation_seed['kb_id']}/generation/drafts",
        json={
            "requirement_context_id": epic6_generation_seed["requirement_context_id"],
            "suggestion_id": epic6_generation_seed["suggestion_id"],
            "target_outline_node": {
                "title": "技术方案",
                "level": 1,
                "sort_order": 0,
            },
            "variable_values": {},
        },
        headers={"X-Operator-Id": "tester"},
    )

    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["task_id"]
    assert data["status"] in {"pending", "running", "completed", "failed"}
