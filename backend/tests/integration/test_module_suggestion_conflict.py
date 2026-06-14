from uuid import uuid4

from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.models.module_assembly_suggestion import ModuleAssemblySuggestion
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus


def test_module_suggestion_persists_conflict_filtered_result(client, db_session, seeded_kb):
    category_id = str(uuid4())
    import_row = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="template.docx",
        file_type=FileType.docx,
        file_size=123,
        storage_path="/tmp/template.docx",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(import_row)
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=import_row.import_id,
        template_name="冲突检测模板",
        template_type=TemplateType.technical_bid,
        product_category_ids=[category_id],
        status=TemplateStatus.published,
        created_by="tester",
    )
    db_session.add(template)
    db_session.flush()

    chapter_allowed = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="项目团队",
        level=1,
        sort_order=0,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    chapter_conflict = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="唯一厂家证明",
        level=1,
        sort_order=1,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add_all([chapter_allowed, chapter_conflict])
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions",
        json={
            "product_category_ids": [category_id],
            "outline_nodes": [{"title": "项目团队", "level": 1, "sort_order": 0}],
            "tender_requirement_context": {"rejection_clauses": ["不得要求唯一厂家证明"]},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200

    saved = (
        db_session.query(ModuleAssemblySuggestion)
        .filter(ModuleAssemblySuggestion.kb_id == seeded_kb.kb_id)
        .order_by(ModuleAssemblySuggestion.created_at.desc())
        .first()
    )
    assert saved is not None
    assert str(chapter_conflict.template_chapter_id) not in saved.suggested_template_chapter_ids
    assert str(chapter_allowed.template_chapter_id) in saved.suggested_template_chapter_ids
    assert saved.risk_flags
