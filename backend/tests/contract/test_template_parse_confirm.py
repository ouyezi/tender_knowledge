from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app
from src.models.candidate_knowledge_stub import CandidateKnowledgeStub
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.template import Template, TemplateType
from src.models.template_chapter import TemplateChapter
from src.models.template_material import TemplateMaterial
from src.models.template_parse_suggestion import TemplateParseSuggestion
from src.models.template_parse_task import TemplateParseTask, TemplateParseTaskStatus


def _seed_parse_ready_task(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="sample-template.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{seeded_kb.kb_id}/sample-template.docx",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.confirmed,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=file_import.import_id,
        template_name="原始模板",
        template_type=TemplateType.technical_bid,
        created_by="admin",
    )
    db_session.add(template)
    db_session.flush()

    parse_task = TemplateParseTask(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        template_id=template.template_id,
        status=TemplateParseTaskStatus.parse_ready,
        trace_id=uuid4(),
    )
    db_session.add(parse_task)
    db_session.flush()

    suggestion = TemplateParseSuggestion(
        parse_task_id=parse_task.parse_task_id,
        kb_id=seeded_kb.kb_id,
        suggested_library_name="餐补技术标模板库",
        suggested_product_category_ids=[],
        suggested_chapter_tree=[
            {
                "temp_id": "n1",
                "parent_temp_id": None,
                "title": "项目概述",
                "level": 1,
                "sort_order": 0,
                "chapter_taxonomy_id": None,
                "product_category_ids": [],
                "required": True,
                "is_fixed_section": True,
                "ignored": False,
            }
        ],
        suggested_materials=[
            {
                "temp_id": "m1",
                "chapter_temp_id": "n1",
                "material_type": "fixed_paragraph",
                "title": "固定说明",
                "extract_as_candidate": True,
            }
        ],
        suggested_candidates=[
            {
                "temp_id": "c1",
                "chapter_temp_id": "n1",
                "title": "候选知识",
                "summary": "候选摘要",
                "content_preview": "候选预览",
                "product_category_ids": [],
            }
        ],
        rationale="rule parse",
    )
    db_session.add(suggestion)
    db_session.commit()
    return parse_task, template


def test_get_parse_suggestion(api_client, db_session, seeded_kb):
    client = TestClient(app)
    parse_task, _ = _seed_parse_ready_task(db_session, seeded_kb)

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-parse/tasks/{parse_task.parse_task_id}/suggestion",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["suggestion_source"] == "rule"
    assert data["suggested_library_name"] == "餐补技术标模板库"
    assert isinstance(data["suggested_chapter_tree"], list)
    assert data["suggested_chapter_tree"][0]["temp_id"] == "n1"


def test_confirm_parse_persists_template_assets(api_client, db_session, seeded_kb):
    client = TestClient(app)
    parse_task, template = _seed_parse_ready_task(db_session, seeded_kb)

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-parse/tasks/{parse_task.parse_task_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "template_library_id": None,
            "template_name": "餐补技术标模板",
            "template_type": "technical_bid",
            "product_category_ids": [],
            "chapters": [
                {
                    "temp_id": "n1",
                    "parent_temp_id": None,
                    "title": "项目概述",
                    "level": 1,
                    "sort_order": 0,
                    "chapter_taxonomy_id": None,
                    "product_category_ids": [],
                    "required": True,
                    "is_fixed_section": True,
                    "ignored": False,
                },
                {
                    "temp_id": "n2",
                    "parent_temp_id": "n1",
                    "title": "实施方案",
                    "level": 2,
                    "sort_order": 0,
                    "chapter_taxonomy_id": None,
                    "product_category_ids": [],
                    "required": False,
                    "is_fixed_section": False,
                    "ignored": False,
                },
            ],
            "materials": [
                {
                    "temp_id": "m1",
                    "chapter_temp_id": "n2",
                    "material_type": "fixed_paragraph",
                    "title": "固定说明",
                    "extract_as_candidate": False,
                    "ignored": False,
                },
                {
                    "temp_id": "m2",
                    "chapter_temp_id": "n1",
                    "material_type": "fixed_paragraph",
                    "title": "忽略素材",
                    "extract_as_candidate": False,
                    "ignored": True,
                },
            ],
            "candidate_actions": [
                {"temp_id": "c1", "candidate_type": "ku", "accepted": True},
                {"temp_id": "c2", "candidate_type": "wiki", "accepted": False},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "confirmed"
    assert data["template_id"] == str(template.template_id)
    assert data["candidate_stubs_created"] == 1
    assert data["structure_locked_at"]

    db_session.refresh(template)
    db_session.refresh(parse_task)
    assert template.confirmed is True
    assert template.structure_locked_at is not None
    assert parse_task.status == TemplateParseTaskStatus.confirmed

    chapters = (
        db_session.query(TemplateChapter)
        .filter(TemplateChapter.template_id == template.template_id)
        .order_by(TemplateChapter.level.asc())
        .all()
    )
    assert len(chapters) == 2
    assert chapters[1].parent_id == chapters[0].template_chapter_id

    materials = (
        db_session.query(TemplateMaterial)
        .filter(TemplateMaterial.template_id == template.template_id)
        .all()
    )
    assert len(materials) == 1
    assert materials[0].title == "固定说明"

    stubs = (
        db_session.query(CandidateKnowledgeStub)
        .filter(CandidateKnowledgeStub.template_id == template.template_id)
        .all()
    )
    assert len(stubs) == 1
    assert stubs[0].title == "候选知识"
