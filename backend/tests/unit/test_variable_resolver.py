import pytest
from uuid import uuid4

from src.models.template_variable import (
    TemplateVariable,
    TemplateVariableStatus,
    TemplateVariableValueType,
)
from src.services.generation.variable_resolver import (
    MissingRequiredVariablesError,
    VariableResolver,
)


def test_missing_required_raises():
    resolver = VariableResolver()
    variables = [
        TemplateVariable(variable_key="project_name", required=True, default_value=None),
    ]
    with pytest.raises(MissingRequiredVariablesError) as exc:
        resolver.validate_and_resolve(variables=variables, values={})
    assert "project_name" in exc.value.missing_keys


def test_default_value_used_when_value_missing():
    resolver = VariableResolver()
    variables = [
        TemplateVariable(
            variable_key="project_name",
            required=True,
            default_value="默认项目",
        ),
    ]
    resolved = resolver.validate_and_resolve(variables=variables, values={})
    assert resolved["project_name"] == "默认项目"


def test_user_value_overrides_default():
    resolver = VariableResolver()
    variables = [
        TemplateVariable(
            variable_key="project_name",
            required=True,
            default_value="默认项目",
        ),
    ]
    resolved = resolver.validate_and_resolve(
        variables=variables,
        values={"project_name": "智慧园区"},
    )
    assert resolved["project_name"] == "智慧园区"


def test_placeholder_replace():
    resolver = VariableResolver()
    text = resolver.replace_placeholders(
        "项目：{{project_name}}",
        resolved={"project_name": "智慧园区"},
    )
    assert text == "项目：智慧园区"


def test_collect_for_template_chapters_loads_active_only(db_session, seeded_kb):
    from src.models.file_import import (
        FileImport,
        FileImportStatus,
        FilePurpose,
        FileType,
        HashStatus,
    )
    from src.models.template import Template, TemplateStatus, TemplateType
    from src.models.template_chapter import TemplateChapter, TemplateChapterStatus

    category_id = str(uuid4())
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="template.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path="/tmp/template.docx",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(file_import)
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=file_import.import_id,
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
        title="技术方案",
        level=1,
        sort_order=0,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add(chapter)
    db_session.flush()

    active_var = TemplateVariable(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        template_chapter_id=chapter.template_chapter_id,
        variable_key="project_name",
        value_type=TemplateVariableValueType.string,
        required=True,
        status=TemplateVariableStatus.active,
    )
    inactive_var = TemplateVariable(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        template_chapter_id=chapter.template_chapter_id,
        variable_key="legacy_key",
        value_type=TemplateVariableValueType.string,
        required=False,
        status=TemplateVariableStatus.inactive,
    )
    db_session.add_all([active_var, inactive_var])
    db_session.commit()

    resolver = VariableResolver()
    rows = resolver.collect_for_template_chapters(
        db_session,
        seeded_kb.kb_id,
        [chapter.template_chapter_id],
    )
    assert len(rows) == 1
    assert rows[0].variable_key == "project_name"
