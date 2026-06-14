import uuid

from sqlalchemy.orm import sessionmaker

from src.models.chapter_draft import ChapterDraft
from src.models.generation_task import GenerationTask, GenerationTaskStatus
from src.services.generation.generation_runner import run_generation_task_in_new_session
from src.services.llm_client import LLMResponse


def _complete_generation_draft(client, db_session, epic6_generation_seed, monkeypatch) -> dict:
    monkeypatch.setattr("src.api.routes.generation.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "src.api.routes.generation.run_generation_task_in_new_session",
        lambda _task_id: None,
    )
    monkeypatch.setattr("src.services.generation.generation_service.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "src.services.generation.generation_service.chat_completion",
        lambda **_kwargs: LLMResponse(
            content='{"paragraphs":[{"text":"总体架构说明","source_ref_ids":["SRC-001"]}]}',
            model="mock-model",
            provider="mock-provider",
        ),
    )
    TestSessionLocal = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    monkeypatch.setattr("src.services.generation.generation_runner.SessionLocal", TestSessionLocal)

    create_resp = client.post(
        f"/api/v1/kbs/{epic6_generation_seed['kb_id']}/generation/drafts",
        json={
            "requirement_context_id": epic6_generation_seed["requirement_context_id"],
            "suggestion_id": epic6_generation_seed["suggestion_id"],
            "target_outline_node": {"title": "技术方案", "level": 1, "sort_order": 0},
            "variable_values": {},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert create_resp.status_code == 202
    task_id = uuid.UUID(create_resp.json()["data"]["task_id"])

    run_generation_task_in_new_session(task_id)

    task = db_session.get(GenerationTask, task_id)
    assert task is not None
    assert task.status == GenerationTaskStatus.completed, f"{task.error_code}: {task.error_message}"
    assert task.draft_id is not None

    draft = db_session.get(ChapterDraft, task.draft_id)
    assert draft is not None

    return {
        "kb_id": epic6_generation_seed["kb_id"],
        "task_id": str(task.task_id),
        "draft_id": str(draft.draft_id),
        "snapshot_id": str(draft.snapshot_id),
        "requirement_context_id": epic6_generation_seed["requirement_context_id"],
    }


def test_get_snapshot_includes_audit_fields(client, db_session, epic6_generation_seed, monkeypatch):
    completed = _complete_generation_draft(client, db_session, epic6_generation_seed, monkeypatch)

    resp = client.get(
        f"/api/v1/kbs/{completed['kb_id']}/generation/snapshots/{completed['snapshot_id']}",
        headers={"X-Operator-Id": "tester"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["snapshot_id"] == completed["snapshot_id"]
    assert data["task_id"] == completed["task_id"]
    assert data["prompt_version"] == "generation-v1.0.0"
    assert isinstance(data["variable_inputs"], dict)
    assert isinstance(data["requirement_context_snapshot"], dict)
    assert data["requirement_context_snapshot"]["requirement_context_id"] == completed[
        "requirement_context_id"
    ]
    assert data["retrieval_trace_summary"] is not None
    assert "trace_id" in data["retrieval_trace_summary"]


def test_get_draft_includes_paragraphs_and_citations(
    client, db_session, epic6_generation_seed, monkeypatch
):
    completed = _complete_generation_draft(client, db_session, epic6_generation_seed, monkeypatch)

    resp = client.get(
        f"/api/v1/kbs/{completed['kb_id']}/generation/drafts/{completed['draft_id']}",
        headers={"X-Operator-Id": "tester"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["draft_id"] == completed["draft_id"]
    assert data["snapshot_id"] == completed["snapshot_id"]
    assert data["paragraphs"]
    assert data["paragraphs"][0]["citations"]
    assert isinstance(data["conflict_hints"], list)
    assert isinstance(data["missing_material_hints"], list)


def test_list_snapshots_and_drafts_with_filters(client, db_session, epic6_generation_seed, monkeypatch):
    completed = _complete_generation_draft(client, db_session, epic6_generation_seed, monkeypatch)

    snapshot_list = client.get(
        f"/api/v1/kbs/{completed['kb_id']}/generation/snapshots",
        params={
            "requirement_context_id": completed["requirement_context_id"],
            "target_title": "技术方案",
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert snapshot_list.status_code == 200
    snapshot_items = snapshot_list.json()["data"]["items"]
    assert snapshot_items
    assert any(item["snapshot_id"] == completed["snapshot_id"] for item in snapshot_items)

    draft_list = client.get(
        f"/api/v1/kbs/{completed['kb_id']}/generation/drafts",
        params={
            "requirement_context_id": completed["requirement_context_id"],
            "target_title": "技术方案",
            "outcome_status": "pending",
            "is_active": True,
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert draft_list.status_code == 200
    draft_items = draft_list.json()["data"]["items"]
    assert draft_items
    assert any(item["draft_id"] == completed["draft_id"] for item in draft_items)
