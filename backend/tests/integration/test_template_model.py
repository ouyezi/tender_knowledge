from uuid import uuid4

from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_parse_task import TemplateParseTask, TemplateParseTaskStatus


def test_create_template_and_parse_task(db_session):
    kb_id = uuid4()
    import_id = uuid4()
    tpl = Template(
        kb_id=kb_id,
        source_import_id=import_id,
        template_name="餐补模板.docx",
        template_type=TemplateType.technical_bid,
        status=TemplateStatus.draft,
        confirmed=False,
        created_by="admin",
    )
    db_session.add(tpl)
    db_session.flush()
    task = TemplateParseTask(
        kb_id=kb_id,
        import_id=import_id,
        template_id=tpl.template_id,
        status=TemplateParseTaskStatus.pending,
        trace_id=uuid4(),
    )
    db_session.add(task)
    db_session.commit()
    assert tpl.template_id is not None
    assert task.parse_task_id is not None


def test_template_parse_task_persists_llm_progress(db_session, seeded_kb):
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="t.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/t.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.template_file,
        created_by="admin",
    )
    db_session.add(imp)
    db_session.flush()
    task = TemplateParseTask(
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        status=TemplateParseTaskStatus.running,
        llm_progress={
            "total_chunks": 3,
            "completed_chunks": 1,
            "failed_chunks": 0,
            "degraded_to_rule": 0,
            "batch_size": 1,
        },
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    assert task.llm_progress["total_chunks"] == 3
