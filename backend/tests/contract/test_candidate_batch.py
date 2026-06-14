from src.models.candidate_knowledge import CandidateKnowledgeStatus
from tests.contract.test_candidates_list import _seed_document_candidate
from tests.contract.test_file_import_confirm import _seed_active_category


def _confirm_payload(category_id: str) -> dict:
    return {
        "confirm_as": "ku",
        "knowledge_type": "solution",
        "title": "云平台架构设计",
        "content": "完整正文内容",
        "product_category_ids": [category_id],
    }


def test_batch_confirm_partial_failure(client, db_session, seeded_kb):
    category = _seed_active_category(db_session, seeded_kb.kb_id)
    candidate1, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate2, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate2.suggested_knowledge_type = None
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/batch/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "items": [
                {
                    "candidate_id": f"doc_{candidate1.candidate_id}",
                    **_confirm_payload(str(category.category_id)),
                },
                {
                    "candidate_id": f"doc_{candidate2.candidate_id}",
                    "confirm_as": "ku",
                    "title": "缺少知识类型",
                    "content": "正文",
                    "product_category_ids": [str(category.category_id)],
                },
            ],
            "batch_comment": "晨间批量确认",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1
    assert data["batch_id"]
    assert data["trace_id"]
    assert data["finished_at"]

    ok_item = next(row for row in data["results"] if row["candidate_id"] == f"doc_{candidate1.candidate_id}")
    assert ok_item["status"] == "published"
    assert ok_item["confirmed_object_type"] == "ku"
    assert ok_item["confirmed_object_id"]
    assert ok_item["error"] is None

    failed_item = next(
        row for row in data["results"] if row["candidate_id"] == f"doc_{candidate2.candidate_id}"
    )
    assert failed_item["status"] == "pending"
    assert failed_item["confirmed_object_type"] is None
    assert failed_item["confirmed_object_id"] is None
    assert failed_item["error"]["code"] == "PUBLISH_VALIDATION_FAILED"


def test_batch_reject_all_rejected(client, db_session, seeded_kb):
    candidate1, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate2, *_ = _seed_document_candidate(db_session, seeded_kb)

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/batch/reject",
        headers={"X-Operator-Id": "admin"},
        json={
            "candidate_ids": [
                f"doc_{candidate1.candidate_id}",
                f"doc_{candidate2.candidate_id}",
            ],
            "review_comment": "低置信度批量忽略",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0
    assert all(item["status"] == "rejected" for item in data["results"])
    assert all(item["error"] is None for item in data["results"])

    db_session.expire_all()
    updated1 = db_session.get(type(candidate1), candidate1.candidate_id)
    updated2 = db_session.get(type(candidate2), candidate2.candidate_id)
    assert updated1 is not None and updated1.status == CandidateKnowledgeStatus.rejected
    assert updated2 is not None and updated2.status == CandidateKnowledgeStatus.rejected


def test_batch_confirm_too_large_returns_413(client, seeded_kb):
    items = [
        {
            "candidate_id": f"doc_fake-{idx}",
            "confirm_as": "ignore",
        }
        for idx in range(101)
    ]
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/batch/confirm",
        headers={"X-Operator-Id": "admin"},
        json={"items": items, "batch_comment": "too large"},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "BATCH_TOO_LARGE"
