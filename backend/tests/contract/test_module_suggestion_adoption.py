from uuid import uuid4

from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus


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


def _create_module_suggestion(client, db_session, seeded_kb) -> str:
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
    db_session.commit()

    create_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions",
        json={
            "product_category_ids": [category_id],
            "outline_nodes": [{"title": "技术方案", "level": 1, "sort_order": 0}],
            "tender_requirement_context": {
                "rejection_clauses": ["禁止要求原厂授权"],
                "score_points": ["可实施性"],
            },
            "retrieval_options": {"top_k": 10},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert create_resp.status_code == 200
    return create_resp.json()["data"]["module_suggestions"][0]["suggestion_id"]


def test_adopt_module_suggestion(client, seeded_kb, db_session):
    suggestion_id = _create_module_suggestion(client, db_session, seeded_kb)
    resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions/{suggestion_id}/adoption",
        json={"status": "adopted", "adoption_reason": "测试采纳"},
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "adopted"
