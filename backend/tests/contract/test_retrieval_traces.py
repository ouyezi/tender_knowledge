from uuid import UUID, uuid4

from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus, RetrievalObjectType


def test_retrieval_traces_list_and_detail(client, db_session, seeded_kb):
    db_session.add(
        RetrievalIndexEntry(
            kb_id=seeded_kb.kb_id,
            object_type=RetrievalObjectType.ku,
            object_id=uuid4(),
            title="技术方案",
            content_text="云架构能力",
            product_category_ids=[],
            status=RetrievalIndexStatus.published,
        )
    )
    db_session.commit()

    search_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/search",
        json={"query": "技术方案", "intent": "knowledge_lookup", "retrieval_options": {"top_k": 5}},
        headers={"X-Operator-Id": "tester"},
    )
    assert search_resp.status_code == 200
    trace_id = search_resp.json()["data"]["trace_id"]

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/traces",
        headers={"X-Operator-Id": "tester"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert any(item["trace_id"] == trace_id for item in items)

    detail_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/traces/{trace_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["trace_id"] == trace_id
    assert detail["intent"] == "knowledge_lookup"
    assert "request_snapshot" in detail
    assert "stages" in detail
    assert "response_summary" in detail


def test_retrieval_trace_detail_not_found(client, seeded_kb):
    trace_id = UUID("00000000-0000-0000-0000-000000000001")
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/traces/{trace_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TRACE_NOT_FOUND"
