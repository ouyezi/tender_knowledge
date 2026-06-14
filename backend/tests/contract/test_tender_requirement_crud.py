def test_create_and_get_tender_requirement(client, seeded_kb):
    create = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/tender-requirements",
        json={
            "title": "Epic6 测试约束",
            "outline_nodes": [{"title": "1.1 总体架构", "level": 2, "sort_order": 1}],
            "score_points": [{"node_ref": "1.1", "text": "架构清晰"}],
            "rejection_clauses": ["未提供资质证明废标"],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert create.status_code == 200
    ctx_id = create.json()["data"]["requirement_context_id"]
    get_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/tender-requirements/{ctx_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["title"] == "Epic6 测试约束"
