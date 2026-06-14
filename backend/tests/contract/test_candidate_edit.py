from uuid import uuid4

from src.models.candidate_knowledge import CandidateKnowledgeStatus
from tests.contract.test_candidates_list import _seed_document_candidate


def test_patch_candidate_title(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate_id = f"doc_{candidate.candidate_id}"

    resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{candidate_id}",
        headers={"X-Operator-Id": "admin"},
        json={"title": "云平台架构设计（修订）"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["candidate_id"] == candidate_id
    assert body["data"]["status"] == "pending"
    assert body["data"]["updated_at"]

    detail = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{candidate_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "云平台架构设计（修订）"


def test_patch_published_candidate_returns_409(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.status = CandidateKnowledgeStatus.published
    db_session.commit()

    candidate_id = f"doc_{candidate.candidate_id}"
    resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{candidate_id}",
        headers={"X-Operator-Id": "admin"},
        json={"title": "不应成功"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CANDIDATE_NOT_EDITABLE"


def test_patch_invalid_taxonomy_returns_422(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate_id = f"doc_{candidate.candidate_id}"

    resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{candidate_id}",
        headers={"X-Operator-Id": "admin"},
        json={"suggested_chapter_taxonomy_id": str(uuid4())},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_TAXONOMY"
