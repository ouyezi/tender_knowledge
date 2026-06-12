from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter
from src.models.template_library import TemplateLibrary, TemplateLibraryType
from src.models.template_publish_snapshot import (
    TemplatePublishObjectType,
    TemplatePublishSnapshot,
)
from src.models.template_rule import TemplateRule, TemplateRuleAction, TemplateRuleType
from src.models.template_variable import TemplateVariable


def _seed_publishable_template(db_session, seeded_kb):
    library = TemplateLibrary(
        kb_id=seeded_kb.kb_id,
        library_name="发布库",
        library_type=TemplateLibraryType.technical,
        created_by="admin",
    )
    db_session.add(library)
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=uuid4(),
        template_library_id=library.template_library_id,
        template_name="模板A",
        template_type=TemplateType.technical_bid,
        confirmed=True,
        created_by="admin",
    )
    db_session.add(template)
    db_session.flush()
    chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        title="章节1",
        level=1,
        sort_order=0,
        required=True,
        parse_source_ref="n1",
    )
    db_session.add(chapter)
    db_session.flush()
    db_session.add(
        TemplateVariable(
            kb_id=seeded_kb.kb_id,
            template_id=template.template_id,
            template_chapter_id=chapter.template_chapter_id,
            variable_key="project_name",
            required=True,
            default_value="默认项目",
        )
    )
    db_session.add(
        TemplateRule(
            kb_id=seeded_kb.kb_id,
            template_id=template.template_id,
            template_chapter_id=chapter.template_chapter_id,
            rule_type=TemplateRuleType.required,
            action=TemplateRuleAction.enable,
        )
    )
    db_session.commit()
    return library, template


def test_publish_template_creates_snapshot(api_client, db_session, seeded_kb):
    client = TestClient(app)
    _library, template = _seed_publishable_template(db_session, seeded_kb)

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/templates/{template.template_id}/publish",
        headers={"X-Operator-Id": "admin"},
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "published"
    assert data["snapshot_id"]

    db_session.refresh(template)
    assert template.status == TemplateStatus.published
    snapshot = (
        db_session.query(TemplatePublishSnapshot)
        .filter(
            TemplatePublishSnapshot.object_type == TemplatePublishObjectType.template,
            TemplatePublishSnapshot.object_id == template.template_id,
        )
        .one_or_none()
    )
    assert snapshot is not None


def test_publish_library_and_filter_published(api_client, db_session, seeded_kb):
    client = TestClient(app)
    library, _template = _seed_publishable_template(db_session, seeded_kb)

    publish_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-libraries/{library.template_library_id}/publish",
        headers={"X-Operator-Id": "admin"},
        json={"cascade_templates": True},
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["data"]["status"] == "published"

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-libraries?status=published",
        headers={"X-Operator-Id": "admin"},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert any(item["template_library_id"] == str(library.template_library_id) for item in items)


def test_publish_template_blocks_missing_required_variable_default(
    api_client,
    db_session,
    seeded_kb,
):
    client = TestClient(app)
    _library, template = _seed_publishable_template(db_session, seeded_kb)
    variable = (
        db_session.query(TemplateVariable)
        .filter(TemplateVariable.template_id == template.template_id)
        .one()
    )
    variable.default_value = None
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/templates/{template.template_id}/publish",
        headers={"X-Operator-Id": "admin"},
        json={},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_STATE"
