from tests.contract.test_candidates_list import _seed_document_candidate


def test_pending_candidate_absent_from_knowledge_units_list(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-units",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    candidate_ids = {item.get("candidate_id") for item in data["items"]}
    assert candidate.candidate_id not in candidate_ids
