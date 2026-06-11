from uuid import UUID, uuid4

from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.classification_reference import (
    ClassificationReference,
    ClassificationType,
    ReferenceObjectType,
)
from src.models.downstream_task_entry import DownstreamTaskEntry
from src.models.file_import import FileImport
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.models.product_category import CategoryStatus, ProductCategory


def _seed_active_category(db_session, kb_id: UUID) -> ProductCategory:
    category = ProductCategory(
        category_id=uuid4(),
        kb_id=kb_id,
        parent_id=None,
        category_name="餐补",
        category_code="meal_allowance",
        status=CategoryStatus.active,
        path="",
        depth=0,
    )
    category.path = f"/{category.category_id}/"
    db_session.add(category)
    db_session.commit()
    return category


def _seed_active_taxonomy(db_session, kb_id: UUID) -> ChapterTaxonomy:
    taxonomy = ChapterTaxonomy(
        taxonomy_id=uuid4(),
        kb_id=kb_id,
        parent_id=None,
        standard_name="费用报销",
        taxonomy_code="expense_claim",
        status=CategoryStatus.active,
        path="",
        depth=0,
    )
    taxonomy.path = f"/{taxonomy.taxonomy_id}/"
    db_session.add(taxonomy)
    db_session.commit()
    return taxonomy


def test_confirm_persists_purpose(client, db_session, uploaded_need_confirm):
    kb_id = uploaded_need_confirm["kb_id"]
    import_id = uploaded_need_confirm["import_id"]
    category = _seed_active_category(db_session, kb_id)
    taxonomy = _seed_active_taxonomy(db_session, kb_id)

    before = db_session.get(FileImport, import_id)
    assert before is not None
    assert before.version == 1

    resp = client.post(
        f"/api/v1/kbs/{kb_id}/file-imports/{import_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "expected_version": before.version,
            "file_purpose": "template_file",
            "product_category_ids": [str(category.category_id)],
            "chapter_taxonomy_id": str(taxonomy.taxonomy_id),
            "enter_parsing": True,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["status"] == "confirmed"
    assert payload["file_purpose"] == "template_file"
    assert payload["product_category_ids"] == [str(category.category_id)]
    assert payload["chapter_taxonomy_id"] == str(taxonomy.taxonomy_id)
    assert payload["version"] == 2
    assert payload["confirmed_by"] == "admin"

    db_session.expire_all()
    updated = db_session.get(FileImport, import_id)
    assert updated is not None
    assert updated.status.value == "confirmed"
    assert updated.file_purpose is not None
    assert updated.file_purpose.value == "template_file"
    assert updated.version == 2
    assert updated.confirmed_by == "admin"
    assert updated.confirmed_at is not None

    refs = (
        db_session.query(ClassificationReference)
        .filter(
            ClassificationReference.object_id == import_id,
            ClassificationReference.object_type == ReferenceObjectType.file_import,
        )
        .all()
    )
    assert len(refs) == 2
    assert {
        (ref.classification_type, ref.classification_id)
        for ref in refs
    } == {
        (ClassificationType.product_category, category.category_id),
        (ClassificationType.chapter_taxonomy, taxonomy.taxonomy_id),
    }

    confirm_audit = (
        db_session.query(ImportAuditLog)
        .filter(
            ImportAuditLog.import_id == import_id,
            ImportAuditLog.action == ImportAuditAction.confirm,
        )
        .one_or_none()
    )
    assert confirm_audit is not None


def test_confirm_version_conflict_409(client, db_session, uploaded_need_confirm):
    kb_id = uploaded_need_confirm["kb_id"]
    import_id = uploaded_need_confirm["import_id"]
    category = _seed_active_category(db_session, kb_id)

    resp = client.post(
        f"/api/v1/kbs/{kb_id}/file-imports/{import_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "expected_version": 999,
            "file_purpose": "template_file",
            "product_category_ids": [str(category.category_id)],
            "enter_parsing": True,
        },
    )

    assert resp.status_code == 409
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "CONFLICT"


def test_ignore_no_downstream(client, db_session, uploaded_need_confirm):
    kb_id = uploaded_need_confirm["kb_id"]
    import_id = uploaded_need_confirm["import_id"]
    record = db_session.get(FileImport, import_id)
    assert record is not None

    resp = client.post(
        f"/api/v1/kbs/{kb_id}/file-imports/{import_id}/ignore",
        headers={"X-Operator-Id": "admin"},
        json={"expected_version": record.version, "reason": "误上传"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "ignored"
    assert data["enter_parsing"] is False
    assert data["version"] == record.version + 1

    db_session.expire_all()
    updated = db_session.get(FileImport, import_id)
    assert updated is not None
    assert updated.status.value == "ignored"
    assert updated.enter_parsing is False

    downstream_count = (
        db_session.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.import_id == import_id)
        .count()
    )
    assert downstream_count == 0
