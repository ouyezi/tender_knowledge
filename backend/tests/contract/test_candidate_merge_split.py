from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeStatus
from tests.contract.test_candidates_list import _seed_document_candidate


def test_merge_two_pending_document_candidates(client, db_session, seeded_kb):
    target, *_ = _seed_document_candidate(db_session, seeded_kb)
    source, *_ = _seed_document_candidate(db_session, seeded_kb)

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/merge",
        headers={"X-Operator-Id": "admin"},
        json={
            "target_candidate_id": f"doc_{target.candidate_id}",
            "source_candidate_ids": [f"doc_{source.candidate_id}"],
            "title": "合并后标题",
            "review_comment": "合并重复候选",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["target_candidate_id"] == f"doc_{target.candidate_id}"
    assert data["merged_count"] == 1
    assert data["status"] == "pending"

    db_session.expire_all()
    source_row = db_session.get(CandidateKnowledge, source.candidate_id)
    target_row = db_session.get(CandidateKnowledge, target.candidate_id)
    assert source_row is not None
    assert target_row is not None
    assert source_row.status == CandidateKnowledgeStatus.merged
    assert str(source_row.merged_into_id) == str(target.candidate_id)
    assert target_row.status == CandidateKnowledgeStatus.pending
    assert target_row.title == "合并后标题"


def test_split_pending_document_candidate_into_two(client, db_session, seeded_kb):
    source, *_ = _seed_document_candidate(db_session, seeded_kb)
    source_id = f"doc_{source.candidate_id}"

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{source_id}/split",
        headers={"X-Operator-Id": "admin"},
        json={
            "splits": [
                {
                    "title": "拆分片段 A",
                    "summary": "A summary",
                    "content": "A content",
                    "candidate_type": "ku",
                    "suggested_product_category_ids": [],
                },
                {
                    "title": "拆分片段 B",
                    "summary": "B summary",
                    "content": "B content",
                    "candidate_type": "ku",
                    "suggested_product_category_ids": [],
                },
            ],
            "review_comment": "按主题拆分",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source_candidate_id"] == source_id
    assert data["source_status"] == "merged"
    assert len(data["new_candidate_ids"]) == 2
    assert all(item.startswith("doc_") for item in data["new_candidate_ids"])

    db_session.expire_all()
    source_row = db_session.get(CandidateKnowledge, source.candidate_id)
    assert source_row is not None
    assert source_row.status == CandidateKnowledgeStatus.merged


def test_merge_with_non_pending_source_returns_409(client, db_session, seeded_kb):
    target, *_ = _seed_document_candidate(db_session, seeded_kb)
    source, *_ = _seed_document_candidate(db_session, seeded_kb)
    source.status = CandidateKnowledgeStatus.published
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/merge",
        headers={"X-Operator-Id": "admin"},
        json={
            "target_candidate_id": f"doc_{target.candidate_id}",
            "source_candidate_ids": [f"doc_{source.candidate_id}"],
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "MERGE_SOURCE_NOT_PENDING"


def test_merge_with_invalid_target_returns_409(client, db_session, seeded_kb):
    target, *_ = _seed_document_candidate(db_session, seeded_kb)
    source, *_ = _seed_document_candidate(db_session, seeded_kb)
    target.status = CandidateKnowledgeStatus.published
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/merge",
        headers={"X-Operator-Id": "admin"},
        json={
            "target_candidate_id": f"doc_{target.candidate_id}",
            "source_candidate_ids": [f"doc_{source.candidate_id}"],
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "MERGE_INVALID_TARGET"
