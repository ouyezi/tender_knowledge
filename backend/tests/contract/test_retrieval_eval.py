from uuid import UUID, uuid4

from src.models.retrieval_eval_case import RetrievalEvalCase, RetrievalEvalCaseStatus
from src.models.retrieval_eval_set import RetrievalEvalSet
from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus, RetrievalObjectType
from src.models.retrieval_trace import RetrievalIntent


def test_strategy_crud_and_activate(client, seeded_kb):
    create_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/strategies",
        json={
            "name": "default-v2",
            "version_tag": "2.0.0",
            "config": {"weights": {"keyword": 0.7}},
            "embedding_config_version": "embed-v1",
            "rerank_config_version": None,
            "prompt_config_version": "prompt-v1",
            "notes": "提高 title BM25 权重",
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert create_resp.status_code == 200
    strategy_id = create_resp.json()["data"]["strategy_version_id"]

    activate_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/strategies/{strategy_id}/activate",
        headers={"X-Operator-Id": "tester"},
    )
    assert activate_resp.status_code == 200
    assert activate_resp.json()["data"]["is_active"] is True

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/strategies?is_active=true",
        headers={"X-Operator-Id": "tester"},
    )
    assert list_resp.status_code == 200
    data = list_resp.json()["data"]
    assert data["total"] >= 1
    assert data["items"][0]["is_active"] is True


def test_eval_sets_cases_and_run(client, db_session, seeded_kb):
    create_set = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/eval/sets",
        json={"name": "核心检索用例", "description": ""},
        headers={"X-Operator-Id": "tester"},
    )
    assert create_set.status_code == 200
    eval_set_id = create_set.json()["data"]["eval_set_id"]

    strategy_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/strategies",
        json={
            "name": "default-v1",
            "version_tag": "1.0.0",
            "config": {},
            "embedding_config_version": "embed-v1",
            "rerank_config_version": None,
            "prompt_config_version": "prompt-v1",
            "notes": "",
        },
        headers={"X-Operator-Id": "tester"},
    )
    strategy_id = strategy_resp.json()["data"]["strategy_version_id"]

    hit_object_id = uuid4()
    db_session.add(
        RetrievalIndexEntry(
            kb_id=seeded_kb.kb_id,
            object_type=RetrievalObjectType.ku,
            object_id=hit_object_id,
            title="售后服务承诺",
            content_text="售后服务承诺包含响应时效",
            status=RetrievalIndexStatus.published,
            product_category_ids=[],
            chapter_taxonomy_id=None,
        )
    )
    db_session.commit()

    create_case = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/eval/sets/{eval_set_id}/cases",
        json={
            "query": "售后服务承诺",
            "intent": "knowledge_lookup",
            "filters": {},
            "expected_object_ids": [str(hit_object_id)],
            "negative_object_ids": [],
            "product_category_ids": [],
            "chapter_taxonomy_ids": [],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert create_case.status_code == 200
    eval_case_id = create_case.json()["data"]["eval_case_id"]

    run_before_confirm = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/eval/runs",
        json={
            "eval_set_id": eval_set_id,
            "strategy_version_id": strategy_id,
            "k": 5,
            "metrics": ["recall_at_k", "precision_at_k", "mrr", "ndcg"],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert run_before_confirm.status_code == 422
    assert run_before_confirm.json()["error"]["code"] == "EVAL_SET_EMPTY"

    confirm_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/eval/cases/{eval_case_id}/confirm",
        json={"confirmed_by": "admin"},
        headers={"X-Operator-Id": "tester"},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["data"]["status"] == "confirmed"

    run_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/eval/runs",
        json={
            "eval_set_id": eval_set_id,
            "strategy_version_id": strategy_id,
            "k": 5,
            "metrics": ["recall_at_k", "precision_at_k", "mrr", "ndcg"],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert run_resp.status_code == 200
    run_data = run_resp.json()["data"]
    assert run_data["eval_run_id"]

    get_run = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/eval/runs/{run_data['eval_run_id']}",
        headers={"X-Operator-Id": "tester"},
    )
    assert get_run.status_code == 200
    metrics = get_run.json()["data"]["metrics"]
    assert "recall_at_k" in metrics
    assert "ndcg" in metrics

    eval_case = db_session.get(RetrievalEvalCase, UUID(eval_case_id))
    assert eval_case is not None
    assert eval_case.status == RetrievalEvalCaseStatus.confirmed


def test_eval_case_reject(client, db_session, seeded_kb):
    eval_set = RetrievalEvalSet(kb_id=seeded_kb.kb_id, name="拒绝集", description="")
    db_session.add(eval_set)
    db_session.flush()
    case = RetrievalEvalCase(
        kb_id=seeded_kb.kb_id,
        eval_set_id=eval_set.eval_set_id,
        query="测试",
        intent=RetrievalIntent.knowledge_lookup,
        filters={},
        expected_object_ids=[],
        negative_object_ids=[],
        product_category_ids=[],
        chapter_taxonomy_ids=[],
    )
    db_session.add(case)
    db_session.commit()

    reject_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/eval/cases/{case.eval_case_id}/reject",
        headers={"X-Operator-Id": "tester"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["data"]["status"] == "rejected"
