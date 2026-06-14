from tests.contract.test_candidates_list import _seed_document_candidate
from tests.contract.test_file_import_confirm import _seed_active_category, _seed_active_taxonomy


def test_list_audit_logs_after_publish(client, db_session, seeded_kb):
    taxonomy = _seed_active_taxonomy(db_session, seeded_kb.kb_id)
    category = _seed_active_category(db_session, seeded_kb.kb_id)
    candidate, file_import, *_ = _seed_document_candidate(db_session, seeded_kb)
    cid = f"doc_{candidate.candidate_id}"

    confirm = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "confirm_as": "ku",
            "knowledge_type": "solution",
            "content": "完整正文内容",
            "product_category_ids": [str(category.category_id)],
            "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
        },
    )
    assert confirm.status_code == 200

    by_candidate = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidate-audit-logs",
        params={"candidate_id": cid, "action": "publish"},
        headers={"X-Operator-Id": "admin"},
    )
    assert by_candidate.status_code == 200
    payload = by_candidate.json()["data"]
    assert payload["total"] >= 1
    assert payload["items"][0]["candidate_id"] == cid
    assert payload["items"][0]["action"] == "publish"
    assert payload["items"][0]["operator_id"] == "admin"

    by_import = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidate-audit-logs",
        params={"import_id": str(file_import.import_id), "action": "publish"},
        headers={"X-Operator-Id": "admin"},
    )
    assert by_import.status_code == 200
    assert by_import.json()["data"]["total"] >= 1


def test_get_audit_log_detail(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    cid = f"doc_{candidate.candidate_id}"

    edit = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}",
        headers={"X-Operator-Id": "admin"},
        json={"title": "审计测试标题"},
    )
    assert edit.status_code == 200

    listed = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidate-audit-logs",
        params={"candidate_id": cid, "action": "edit"},
        headers={"X-Operator-Id": "admin"},
    )
    audit_id = listed.json()["data"]["items"][0]["audit_id"]

    detail = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidate-audit-logs/{audit_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["audit_id"] == audit_id
    assert detail.json()["data"]["action"] == "edit"


def test_get_audit_log_not_found(client, seeded_kb):
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidate-audit-logs/00000000-0000-0000-0000-000000000001",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "AUDIT_LOG_NOT_FOUND"
