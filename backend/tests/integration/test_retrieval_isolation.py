from uuid import uuid4

from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus, RetrievalObjectType
from tests.contract.test_candidates_list import _seed_document_candidate


def test_pending_candidates_do_not_appear_in_retrieval_search(client, db_session, seeded_kb):
    pending_candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    db_session.add(
        RetrievalIndexEntry(
            kb_id=seeded_kb.kb_id,
            object_type=RetrievalObjectType.ku,
            object_id=uuid4(),
            title="已发布知识点",
            content_text="可检索内容",
            product_category_ids=[],
            status=RetrievalIndexStatus.published,
        )
    )
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/search",
        json={
            "query": "云平台架构设计",
            "intent": "knowledge_lookup",
            "retrieval_options": {"top_k": 20, "enable_bm25": True, "enable_vector": False},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    titles = {item["title"] for item in data["items"]}
    assert pending_candidate.title not in titles
