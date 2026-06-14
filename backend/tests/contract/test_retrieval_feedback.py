from uuid import UUID, uuid4

from src.models.retrieval_eval_case import RetrievalEvalCase
from src.models.retrieval_eval_set import RetrievalEvalSet
from src.models.retrieval_trace import RetrievalIntent, RetrievalTrace, RetrievalTraceStatus


def _seed_trace(db_session, kb_id):
    trace = RetrievalTrace(
        kb_id=kb_id,
        intent=RetrievalIntent.knowledge_lookup,
        request_snapshot={
            "query": "技术方案",
            "intent": RetrievalIntent.knowledge_lookup.value,
            "product_category_ids": [str(uuid4())],
            "chapter_taxonomy_ids": [str(uuid4())],
        },
        stages={"recall": {"count": 1}},
        status=RetrievalTraceStatus.success,
    )
    db_session.add(trace)
    db_session.commit()
    db_session.refresh(trace)
    return trace


def test_create_feedback_and_list_feedback(client, db_session, seeded_kb):
    trace = _seed_trace(db_session, seeded_kb.kb_id)

    bad_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/feedback",
        json={
            "trace_id": str(trace.trace_id),
            "feedback_type": "false_negative",
            "object_type": "ku",
            "object_id": str(uuid4()),
            "rank_position": 1,
            "expected_object_ids": [],
            "comment": "",
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert bad_resp.status_code == 422
    assert bad_resp.json()["error"]["code"] == "FALSE_NEGATIVE_MISSING_EXPECTATION"

    good_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/feedback",
        json={
            "trace_id": str(trace.trace_id),
            "feedback_type": "useful",
            "object_type": "ku",
            "object_id": str(uuid4()),
            "rank_position": 1,
            "expected_object_ids": [],
            "comment": "命中需求",
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert good_resp.status_code == 200
    data = good_resp.json()["data"]
    assert data["feedback_id"]
    assert data["trace_id"] == str(trace.trace_id)
    assert data["feedback_type"] == "useful"

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/feedback?trace_id={trace.trace_id}&feedback_type=useful",
        headers={"X-Operator-Id": "tester"},
    )
    assert list_resp.status_code == 200
    listed = list_resp.json()["data"]
    assert listed["total"] == 1
    assert listed["items"][0]["feedback_id"] == data["feedback_id"]


def test_promote_feedback_to_eval_case(client, db_session, seeded_kb):
    trace = _seed_trace(db_session, seeded_kb.kb_id)
    eval_set = RetrievalEvalSet(kb_id=seeded_kb.kb_id, name="核心评测集", description="")
    db_session.add(eval_set)
    db_session.commit()
    db_session.refresh(eval_set)

    feedback_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/feedback",
        json={
            "trace_id": str(trace.trace_id),
            "feedback_type": "false_negative",
            "object_type": "ku",
            "object_id": str(uuid4()),
            "rank_position": 3,
            "expected_object_ids": [str(uuid4())],
            "comment": "",
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert feedback_resp.status_code == 200
    feedback_id = feedback_resp.json()["data"]["feedback_id"]

    promote_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/feedback/{feedback_id}/promote-to-eval-case",
        json={
            "eval_set_id": str(eval_set.eval_set_id),
            "expected_object_ids": [str(uuid4())],
            "negative_object_ids": [],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert promote_resp.status_code == 200
    payload = promote_resp.json()["data"]
    assert payload["status"] == "pending"
    assert payload["eval_case_id"]

    row = db_session.get(RetrievalEvalCase, UUID(payload["eval_case_id"]))
    assert row is not None
    assert row.created_from.value == "user_feedback"
    assert row.source_feedback_id is not None
