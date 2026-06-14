from uuid import UUID, uuid4

from src.models.retrieval_index_entry import (
    RetrievalIndexEntry,
    RetrievalIndexStatus,
    RetrievalObjectType,
)
from src.models.retrieval_trace import RetrievalIntent, RetrievalTrace


def test_retrieval_search_returns_published_hits_only(client, db_session, seeded_kb):
    category_id = str(uuid4())
    hit_entry = RetrievalIndexEntry(
        kb_id=seeded_kb.kb_id,
        object_type=RetrievalObjectType.ku,
        object_id=uuid4(),
        title="云平台架构设计",
        content_text="技术方案与部署拓扑",
        product_category_ids=[category_id],
        knowledge_type="solution",
        status=RetrievalIndexStatus.published,
    )
    deprecated_entry = RetrievalIndexEntry(
        kb_id=seeded_kb.kb_id,
        object_type=RetrievalObjectType.wiki,
        object_id=uuid4(),
        title="云平台架构旧版本",
        content_text="过时内容",
        product_category_ids=[category_id],
        status=RetrievalIndexStatus.deprecated,
    )
    db_session.add_all([hit_entry, deprecated_entry])
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/search",
        json={
            "query": "云平台架构",
            "intent": "knowledge_lookup",
            "product_category_ids": [category_id],
            "object_types": ["ku", "wiki"],
            "retrieval_options": {"top_k": 10, "enable_bm25": True, "enable_vector": False},
            "return_options": {"include_trace": True, "include_score_detail": True},
        },
        headers={"X-Operator-Id": "tester"},
    )

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["trace_id"]
    assert payload["intent"] == "knowledge_lookup"
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["object_type"] == "ku"
    assert item["object_id"] == str(hit_entry.object_id)
    assert item["score"] > 0
    assert "score_detail" in item
    assert item["score_detail"]["keyword"] >= 0

    trace = (
        db_session.query(RetrievalTrace)
        .filter(
            RetrievalTrace.kb_id == seeded_kb.kb_id,
            RetrievalTrace.trace_id == UUID(payload["trace_id"]),
        )
        .one_or_none()
    )
    assert trace is not None
    assert trace.intent == RetrievalIntent.knowledge_lookup
