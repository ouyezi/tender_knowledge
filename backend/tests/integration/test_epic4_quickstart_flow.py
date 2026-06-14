"""Epic 4 quickstart scenarios 0–9 (API-level smoke)."""

from tests.contract.test_candidates_list import _seed_document_candidate
from tests.contract.test_file_import_confirm import _seed_active_category, _seed_active_taxonomy


def test_epic4_quickstart_scenarios(client, db_session, seeded_kb):
    taxonomy = _seed_active_taxonomy(db_session, seeded_kb.kb_id)
    category = _seed_active_category(db_session, seeded_kb.kb_id)
    kb_id = seeded_kb.kb_id
    headers = {"X-Operator-Id": "admin"}

    # Scenario 0: pending candidates exist
    candidate_a, import_a, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate_b, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate_c, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate_d, *_ = _seed_document_candidate(db_session, seeded_kb)
    cid_a = f"doc_{candidate_a.candidate_id}"
    cid_b = f"doc_{candidate_b.candidate_id}"
    cid_c = f"doc_{candidate_c.candidate_id}"
    cid_d = f"doc_{candidate_d.candidate_id}"

    candidate_a.suggested_chapter_taxonomy_id = taxonomy.taxonomy_id
    db_session.commit()

    pending_list = client.get(
        f"/api/v1/kbs/{kb_id}/candidates",
        params={"status": "pending"},
        headers=headers,
    )
    assert pending_list.status_code == 200
    assert pending_list.json()["data"]["total"] >= 3

    # Scenario 1: list filters
    filtered = client.get(
        f"/api/v1/kbs/{kb_id}/candidates",
        params={
            "status": "pending",
            "import_id": str(import_a.import_id),
            "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
        },
        headers=headers,
    )
    assert filtered.status_code == 200
    filtered_ids = {item["candidate_id"] for item in filtered.json()["data"]["items"]}
    assert cid_a in filtered_ids
    assert filtered.json()["data"]["items"][0]["confidence_score"] is not None

    # Scenario 2: edit
    patch = client.patch(
        f"/api/v1/kbs/{kb_id}/candidates/{cid_a}",
        headers=headers,
        json={"title": "修订标题", "summary": "修订摘要"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["status"] == "pending"
    detail = client.get(f"/api/v1/kbs/{kb_id}/candidates/{cid_a}", headers=headers)
    assert detail.json()["data"]["title"] == "修订标题"

    # Scenario 3: publish as KU
    confirm = client.post(
        f"/api/v1/kbs/{kb_id}/candidates/{cid_a}/confirm",
        headers=headers,
        json={
            "confirm_as": "ku",
            "knowledge_type": "solution",
            "content": "完整正文内容",
            "product_category_ids": [str(category.category_id)],
            "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
            "searchable": True,
            "review_comment": "quickstart 单条发布",
        },
    )
    assert confirm.status_code == 200
    confirm_data = confirm.json()["data"]
    assert confirm_data["status"] == "published"
    assert confirm_data["confirmed_object_id"]

    pending_after = client.get(
        f"/api/v1/kbs/{kb_id}/candidates",
        params={"status": "pending"},
        headers=headers,
    )
    pending_ids = {item["candidate_id"] for item in pending_after.json()["data"]["items"]}
    assert cid_a not in pending_ids

    ku_list = client.get(f"/api/v1/kbs/{kb_id}/knowledge-units", headers=headers)
    assert ku_list.status_code == 200
    ku_candidate_ids = {item["candidate_id"] for item in ku_list.json()["data"]["items"]}
    assert str(candidate_a.candidate_id) in ku_candidate_ids

    # Scenario 4: ignore
    ignore = client.post(
        f"/api/v1/kbs/{kb_id}/candidates/{cid_d}/confirm",
        headers=headers,
        json={"confirm_as": "ignore", "review_comment": "低价值忽略"},
    )
    assert ignore.status_code == 200
    assert ignore.json()["data"]["status"] == "rejected"

    # Scenario 5: merge
    merge = client.post(
        f"/api/v1/kbs/{kb_id}/candidates/merge",
        headers=headers,
        json={
            "target_candidate_id": cid_c,
            "source_candidate_ids": [cid_b],
            "title": "合并后标题",
            "review_comment": "重复段落合并",
        },
    )
    assert merge.status_code == 200
    assert merge.json()["data"]["merged_count"] == 1

    # Scenario 6: batch confirm (use fresh candidates)
    candidate_d, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate_e, *_ = _seed_document_candidate(db_session, seeded_kb)
    cid_d = f"doc_{candidate_d.candidate_id}"
    cid_e = f"doc_{candidate_e.candidate_id}"

    batch = client.post(
        f"/api/v1/kbs/{kb_id}/candidates/batch/confirm",
        headers=headers,
        json={
            "items": [
                {
                    "candidate_id": cid_d,
                    "confirm_as": "ku",
                    "knowledge_type": "solution",
                    "content": "完整正文内容",
                    "product_category_ids": [str(category.category_id)],
                    "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
                },
                {"candidate_id": cid_e, "confirm_as": "ignore"},
            ],
            "batch_comment": "quickstart batch",
        },
    )
    assert batch.status_code == 200
    batch_data = batch.json()["data"]
    assert batch_data["succeeded"] == 2
    assert batch_data["failed"] == 0
    batch_id = batch_data["batch_id"]

    # Scenario 7: audit logs
    audit_by_candidate = client.get(
        f"/api/v1/kbs/{kb_id}/candidate-audit-logs",
        params={"candidate_id": cid_a},
        headers=headers,
    )
    assert audit_by_candidate.status_code == 200
    actions = {item["action"] for item in audit_by_candidate.json()["data"]["items"]}
    assert "publish" in actions
    assert "edit" in actions

    audit_by_batch = client.get(
        f"/api/v1/kbs/{kb_id}/candidate-audit-logs",
        params={"batch_id": batch_id},
        headers=headers,
    )
    assert audit_by_batch.status_code == 200
    assert audit_by_batch.json()["data"]["total"] >= 1

    # Scenario 8: publish failure + retry
    candidate_f, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate_f.content = ""
    candidate_f.suggested_knowledge_type = None
    db_session.commit()
    cid_f = f"doc_{candidate_f.candidate_id}"
    fail = client.post(
        f"/api/v1/kbs/{kb_id}/candidates/{cid_f}/confirm",
        headers=headers,
        json={
            "confirm_as": "ku",
            "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
        },
    )
    assert fail.status_code == 422

    retry = client.post(
        f"/api/v1/kbs/{kb_id}/candidates/{cid_f}/retry-publish",
        headers=headers,
        json={
            "confirm_as": "ku",
            "knowledge_type": "solution",
            "content": "完整正文内容",
            "product_category_ids": [str(category.category_id)],
            "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
        },
    )
    assert retry.status_code == 200
    assert retry.json()["data"]["status"] == "published"

    audit_retry = client.get(
        f"/api/v1/kbs/{kb_id}/candidate-audit-logs",
        params={"candidate_id": cid_f},
        headers=headers,
    )
    retry_actions = [item["action"] for item in audit_retry.json()["data"]["items"]]
    assert "publish_failed" in retry_actions
    assert "publish" in retry_actions

    # Scenario 9: retrieval isolation
    candidate_g, *_ = _seed_document_candidate(db_session, seeded_kb)
    isolation = client.get(
        f"/api/v1/kbs/{kb_id}/knowledge-units",
        params={"status": "published"},
        headers=headers,
    )
    assert isolation.status_code == 200
    isolated = [
        item
        for item in isolation.json()["data"]["items"]
        if item.get("candidate_id") == str(candidate_g.candidate_id)
    ]
    assert len(isolated) == 0
