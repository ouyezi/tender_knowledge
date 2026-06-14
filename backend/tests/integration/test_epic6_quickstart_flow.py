import uuid

from sqlalchemy.orm import sessionmaker

from src.models.chapter_draft import ChapterDraft
from src.models.generation_task import GenerationTask, GenerationTaskStatus
from src.services.generation.generation_runner import run_generation_task_in_new_session
from src.services.llm_client import LLMResponse


def test_epic6_quickstart_flow_completes_and_binds_citations(
    client, db_session, epic6_generation_seed, monkeypatch
):
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
    assert draft.paragraphs
    assert draft.paragraphs[0]["citations"]
