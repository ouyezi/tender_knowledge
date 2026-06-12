from fastapi.testclient import TestClient

from src.main import app
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.template import Template, TemplateType
from src.models.template_audit_log import TemplateAuditAction, TemplateAuditLog
from src.models.template_chapter import TemplateChapter


def _seed_template_with_chapters(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="tree.docx",
        file_type=FileType.docx,
        file_size=120,
        storage_path=f"{seeded_kb.kb_id}/tree.docx",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.confirmed,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()
    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=file_import.import_id,
        template_name="章节树模板",
        template_type=TemplateType.technical_bid,
        confirmed=True,
        created_by="admin",
    )
    db_session.add(template)
    db_session.flush()

    root = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="项目概述",
        level=1,
        sort_order=0,
        required=True,
    )
    db_session.add(root)
    db_session.flush()
    child = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=root.template_chapter_id,
        title="实施方案",
        level=2,
        sort_order=0,
    )
    db_session.add(child)
    db_session.commit()
    return template, root, child


def test_get_tree_and_batch_update_success(api_client, db_session, seeded_kb):
    client = TestClient(app)
    template, root, child = _seed_template_with_chapters(db_session, seeded_kb)

    tree_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/templates/{template.template_id}/chapters/tree",
        headers={"X-Operator-Id": "admin"},
    )
    assert tree_resp.status_code == 200
    roots = tree_resp.json()["data"]["roots"]
    assert len(roots) == 1
    assert roots[0]["template_chapter_id"] == str(root.template_chapter_id)
    assert roots[0]["children"][0]["template_chapter_id"] == str(child.template_chapter_id)

    db_session.refresh(template)
    payload = {
        "expected_template_updated_at": template.updated_at.isoformat(),
        "chapters": [
            {
                "template_chapter_id": str(root.template_chapter_id),
                "parent_id": None,
                "title": "项目概述(更新)",
                "level": 1,
                "sort_order": 0,
                "chapter_taxonomy_id": None,
                "product_category_ids": [],
                "required": True,
                "is_fixed_section": True,
                "ignored": False,
            },
            {
                "template_chapter_id": str(child.template_chapter_id),
                "parent_id": None,
                "title": "实施方案(提升为根节点)",
                "level": 1,
                "sort_order": 1,
                "chapter_taxonomy_id": None,
                "product_category_ids": [],
                "required": False,
                "is_fixed_section": False,
                "ignored": False,
            },
        ],
    }
    update_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/templates/{template.template_id}/chapters/batch-update",
        headers={"X-Operator-Id": "admin"},
        json=payload,
    )
    assert update_resp.status_code == 200
    body = update_resp.json()["data"]
    assert body["audit_id"]
    assert len(body["roots"]) == 2

    db_session.refresh(root)
    db_session.refresh(child)
    assert root.level == 1
    assert child.parent_id is None
    assert child.level == 1

    audit = (
        db_session.query(TemplateAuditLog)
        .filter(
            TemplateAuditLog.template_id == template.template_id,
            TemplateAuditLog.action == TemplateAuditAction.chapter_update,
        )
        .one_or_none()
    )
    assert audit is not None


def test_batch_update_rejects_invalid_level(api_client, db_session, seeded_kb):
    client = TestClient(app)
    template, root, child = _seed_template_with_chapters(db_session, seeded_kb)
    payload = {
        "chapters": [
            {
                "template_chapter_id": str(root.template_chapter_id),
                "parent_id": None,
                "title": "项目概述",
                "level": 1,
                "sort_order": 0,
                "chapter_taxonomy_id": None,
                "product_category_ids": [],
                "required": True,
                "is_fixed_section": False,
                "ignored": False,
            },
            {
                "template_chapter_id": str(child.template_chapter_id),
                "parent_id": str(root.template_chapter_id),
                "title": "实施方案",
                "level": 3,
                "sort_order": 0,
                "chapter_taxonomy_id": None,
                "product_category_ids": [],
                "required": False,
                "is_fixed_section": False,
                "ignored": False,
            },
        ]
    }
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/templates/{template.template_id}/chapters/batch-update",
        headers={"X-Operator-Id": "admin"},
        json=payload,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_TREE"
