from uuid import uuid4

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
