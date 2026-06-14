from tests.contract.test_candidates_list import _seed_document_candidate
from tests.contract.test_file_import_confirm import _seed_active_category, _seed_active_taxonomy


def test_publish_ku_then_list_and_retry_idempotent(client, db_session, seeded_kb):
    category = _seed_active_category(db_session, seeded_kb.kb_id)
    taxonomy = _seed_active_taxonomy(db_session, seeded_kb.kb_id)
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate_id = f"doc_{candidate.candidate_id}"
    payload = {
        "confirm_as": "ku",
        "knowledge_type": "solution",
        "title": "云平台架构设计",
        "content": "完整正文内容",
        "product_category_ids": [str(category.category_id)],
        "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
        "searchable": True,
    }

    confirm_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{candidate_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json=payload,
    )
    assert confirm_resp.status_code == 200
    first_data = confirm_resp.json()["data"]
    assert first_data["status"] == "published"
    assert first_data["confirmed_object_type"] == "ku"

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-units",
        headers={"X-Operator-Id": "admin"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    matched = [item for item in items if item["candidate_id"] == str(candidate.candidate_id)]
    assert len(matched) == 1

    retry_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{candidate_id}/retry-publish",
        headers={"X-Operator-Id": "admin"},
        json=payload,
    )
    assert retry_resp.status_code == 200
    retry_data = retry_resp.json()["data"]
    assert retry_data["idempotent"] is True
    assert retry_data["confirmed_object_id"] == first_data["confirmed_object_id"]
