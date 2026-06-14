import uuid
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from src.models.chapter_draft import ChapterDraft
from src.models.generation_snapshot import GenerationSnapshot
from src.models.generation_task import GenerationTask, GenerationTaskStatus
from src.models.module_assembly_suggestion import ModuleAssemblySuggestion
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.models.tender_requirement_context import TenderRequirementContext
from src.schemas.generation import UserChapterSelection
from src.services.generation.generation_runner import run_generation_task_in_new_session
from src.services.generation.input_priority_resolver import InputPriorityResolver
from src.services.llm_client import LLMResponse
from tests.conftest import _seed_file_import


def test_conflict_template_excluded_from_catalog_and_hints_emitted(
    client, db_session, seeded_kb, monkeypatch
):
    category_id = str(uuid4())
    template_import = _seed_file_import(db_session, seeded_kb.kb_id, name="conflict-template.docx")
    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=template_import.import_id,
        template_name="冲突模板",
        template_type=TemplateType.technical_bid,
        product_category_ids=[category_id],
        status=TemplateStatus.published,
        created_by="tester",
    )
    db_session.add(template)
    db_session.flush()

    safe_chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="技术方案",
        level=1,
        sort_order=0,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    conflict_chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="原厂授权说明",
        level=2,
        sort_order=1,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add_all([safe_chapter, conflict_chapter])
    db_session.commit()

    tender_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/tender-requirements",
        json={
            "title": "冲突优先级测试",
            "outline_nodes": [{"title": "技术方案", "level": 1, "sort_order": 0}],
            "rejection_clauses": ["禁止要求原厂授权"],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert tender_resp.status_code == 200
    requirement_context_id = tender_resp.json()["data"]["requirement_context_id"]

    suggestion_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions",
        json={
            "product_category_ids": [category_id],
            "requirement_context_id": requirement_context_id,
            "outline_nodes": [{"title": "技术方案", "level": 1, "sort_order": 0}],
            "tender_requirement_context": {
                "rejection_clauses": ["禁止要求原厂授权"],
            },
            "retrieval_options": {"top_k": 10},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert suggestion_resp.status_code == 200
    suggestion_id = suggestion_resp.json()["data"]["module_suggestions"][0]["suggestion_id"]

    suggestion = db_session.get(ModuleAssemblySuggestion, uuid.UUID(suggestion_id))
    assert suggestion is not None
    conflict_chapter_id = str(conflict_chapter.template_chapter_id)
    safe_chapter_id = str(safe_chapter.template_chapter_id)
    suggestion.suggested_template_chapter_ids = [safe_chapter_id, conflict_chapter_id]
    suggestion.knowledge_pack_snapshot = [
        {
            "type": "template_chapter",
            "object_id": conflict_chapter_id,
            "title": conflict_chapter.title,
            "excerpt": conflict_chapter.title,
        }
    ]
    db_session.commit()

    adopt_resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions/{suggestion_id}/adoption",
        json={"status": "adopted", "adoption_reason": "测试采纳"},
        headers={"X-Operator-Id": "tester"},
    )
    assert adopt_resp.status_code == 200

    user_selection = {
        "template_chapter_id": conflict_chapter_id,
        "enabled": True,
        "source": "user_manual",
    }

    monkeypatch.setattr("src.api.routes.generation.is_llm_available", lambda: True)
    monkeypatch.setattr(
        "src.api.routes.generation.run_generation_task_in_new_session",
        lambda _task_id: None,
    )
    monkeypatch.setattr("src.services.generation.generation_service.is_llm_available", lambda: True)

    def _mock_chat_completion(**_kwargs):
        return LLMResponse(
            content=(
                '{"paragraphs":[{"text":"引用冲突章节","source_ref_ids":["SRC-001"]},'
                '{"text":"引用安全章节","source_ref_ids":["SRC-002"]}]}'
            ),
            model="mock-model",
            provider="mock-provider",
        )

    monkeypatch.setattr("src.services.generation.generation_service.chat_completion", _mock_chat_completion)
    TestSessionLocal = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    monkeypatch.setattr("src.services.generation.generation_runner.SessionLocal", TestSessionLocal)

    create_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/generation/drafts",
        json={
            "requirement_context_id": requirement_context_id,
            "suggestion_id": suggestion_id,
            "target_outline_node": {"title": "技术方案", "level": 1, "sort_order": 0},
            "product_category_ids": [category_id],
            "variable_values": {},
            "user_chapter_selections": [user_selection],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert create_resp.status_code == 202
    task_id = uuid.UUID(create_resp.json()["data"]["task_id"])

    run_generation_task_in_new_session(task_id)

    task = db_session.get(GenerationTask, task_id)
    assert task is not None
    assert task.status == GenerationTaskStatus.completed, f"{task.error_code}: {task.error_message}"
    assert task.request_snapshot.get("user_chapter_selections") == [user_selection]

    draft = db_session.get(ChapterDraft, task.draft_id)
    assert draft is not None
    assert draft.conflict_hints, "冲突模板引用应产生 conflict_hints"
    conflict_hint_ids = {
        item.get("template_chapter_id") for item in draft.conflict_hints if item.get("template_chapter_id")
    }
    assert conflict_chapter_id in conflict_hint_ids

    snapshot = db_session.get(GenerationSnapshot, draft.snapshot_id)
    assert snapshot is not None
    db_session.refresh(snapshot)
    assert snapshot.input_priority_layers.get("user_chapter_selections") == [user_selection]

    context = db_session.get(TenderRequirementContext, uuid.UUID(requirement_context_id))
    db_session.refresh(suggestion)
    resolved = InputPriorityResolver().resolve(
        requirement_context=context,
        suggestion=suggestion,
        target_outline_node={"title": "技术方案", "level": 1, "sort_order": 0},
        user_chapter_selections=[UserChapterSelection(**user_selection)],
        resolved_variables={},
        conflict_template_ids={conflict_chapter_id},
    )
    assert not any(
        conflict_chapter_id in line for line in resolved.layers["template_hints"]
    ), "冲突模板不应被 L6 默认采用"
    assert any(
        item.object_id == safe_chapter_id
        for item in resolved.source_catalog
        if item.type == "template_chapter"
    )
