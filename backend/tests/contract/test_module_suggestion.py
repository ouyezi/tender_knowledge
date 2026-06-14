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


def test_create_and_get_module_suggestion(client, db_session, seeded_kb):
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

    chapter_ok = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="技术方案",
        level=1,
        sort_order=0,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    chapter_conflict = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="原厂授权证明",
        level=1,
        sort_order=1,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add_all([chapter_ok, chapter_conflict])
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
            "return_options": {"include_trace": True, "include_score_detail": True},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert create_resp.status_code == 200
    data = create_resp.json()["data"]
    assert data["trace_id"]
    assert data["module_suggestions"]
    suggestion = data["module_suggestions"][0]
    assert str(chapter_ok.template_chapter_id) in suggestion["suggested_template_chapter_ids"]
    assert str(chapter_conflict.template_chapter_id) not in suggestion["suggested_template_chapter_ids"]
    assert suggestion["risk_flags"]

    suggestion_id = suggestion["suggestion_id"]
    get_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions/{suggestion_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert get_resp.status_code == 200
    fetched = get_resp.json()["data"]
    assert fetched["suggestion_id"] == suggestion_id
