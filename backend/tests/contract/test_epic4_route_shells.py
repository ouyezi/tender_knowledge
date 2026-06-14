def test_list_knowledge_units_empty(client, seeded_kb):
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-units",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


def test_list_candidate_audit_logs_empty(client, seeded_kb):
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidate-audit-logs",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


def test_list_wikis_empty(client, seeded_kb):
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/wikis",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


def test_list_manual_assets_empty(client, seeded_kb):
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/manual-assets",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []
