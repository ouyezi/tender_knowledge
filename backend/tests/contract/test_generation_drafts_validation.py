from uuid import UUID, uuid4

from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.models.module_assembly_suggestion import ModuleAssemblySuggestion
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.models.template_variable import (
    TemplateVariable,
    TemplateVariableStatus,
    TemplateVariableValueType,
)


def _seed_file_import(db_session, kb_id, *, name: str) -> FileImport:
    item = FileImport(
        kb_id=kb_id,
        file_name=name,
        file_type=FileType.docx,
        file_size=1024,
        storage_path=f"/tmp/{name}",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(item)
    db_session.flush()
    return item


def _seed_epic6_draft_preflight_fixture(client, db_session, seeded_kb) -> dict[str, str]:
    category_id = str(uuid4())
    template_import = _seed_file_import(db_session, seeded_kb.kb_id, name="template.docx")
    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=template_import.import_id,
        template_name="技术标模板",
        template_type=TemplateType.technical_bid,
        product_category_ids=[category_id],
        status=TemplateStatus.published,
        created_by="tester",
    )
    db_session.add(template)
    db_session.flush()

    chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="技术方案",
        level=1,
        sort_order=0,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add(chapter)
    db_session.flush()

    db_session.add(
        TemplateVariable(
            kb_id=seeded_kb.kb_id,
            template_id=template.template_id,
            template_chapter_id=chapter.template_chapter_id,
            variable_key="project_name",
            value_type=TemplateVariableValueType.string,
            required=True,
            default_value=None,
            status=TemplateVariableStatus.active,
        )
    )
    db_session.commit()

    tender_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/tender-requirements",
        json={
            "title": "Epic6 生成预检",
            "outline_nodes": [{"title": "技术方案", "level": 1, "sort_order": 0}],
            "score_points": [{"node_ref": "1", "text": "可实施性"}],
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
                "score_points": ["可实施性"],
            },
            "retrieval_options": {"top_k": 10},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert suggestion_resp.status_code == 200
    suggestion_id = suggestion_resp.json()["data"]["module_suggestions"][0]["suggestion_id"]

    adopt_resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions/{suggestion_id}/adoption",
        json={"status": "adopted", "adoption_reason": "测试采纳"},
        headers={"X-Operator-Id": "tester"},
    )
    assert adopt_resp.status_code == 200

    return {
        "requirement_context_id": requirement_context_id,
        "suggestion_id": suggestion_id,
    }


def test_create_draft_unpublished_asset_returns_422(
    client, seeded_kb, db_session, monkeypatch
):
    fixture = _seed_epic6_draft_preflight_fixture(client, db_session, seeded_kb)
    monkeypatch.setattr("src.api.routes.generation.is_llm_available", lambda: True)

    suggestion = (
        db_session.query(ModuleAssemblySuggestion)
        .filter(ModuleAssemblySuggestion.suggestion_id == UUID(fixture["suggestion_id"]))
        .one()
    )
    unpublished_chapter_id = suggestion.suggested_template_chapter_ids[0]
    chapter = db_session.get(TemplateChapter, UUID(str(unpublished_chapter_id)))
    chapter.status = TemplateChapterStatus.draft
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/generation/drafts",
        json={
            "requirement_context_id": fixture["requirement_context_id"],
            "suggestion_id": fixture["suggestion_id"],
            "target_outline_node": {
                "title": "技术方案",
                "level": 1,
                "sort_order": 0,
            },
            "variable_values": {"project_name": "智慧园区一期"},
        },
        headers={"X-Operator-Id": "tester"},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ASSET_NOT_PUBLISHED"
    assert resp.json()["error"]["details"]["assets"]


def test_create_draft_missing_variables_returns_422(client, seeded_kb, db_session):
    fixture = _seed_epic6_draft_preflight_fixture(client, db_session, seeded_kb)

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/generation/drafts",
        json={
            "requirement_context_id": fixture["requirement_context_id"],
            "suggestion_id": fixture["suggestion_id"],
            "target_outline_node": {
                "title": "技术方案",
                "level": 1,
                "sort_order": 0,
            },
            "variable_values": {},
        },
        headers={"X-Operator-Id": "tester"},
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MISSING_REQUIRED_VARIABLES"
    assert "project_name" in resp.json()["error"]["details"]["missing_keys"]
