from uuid import uuid4

from src.models.document import Document, DocumentSourceType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus


def _seed_import(db_session, kb_id):
    imp = FileImport(
        kb_id=kb_id,
        file_name="del-test.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="/tmp/del-test.docx",
        status=FileImportStatus.completed,
        file_purpose=FilePurpose.actual_bid,
        created_by="tester",
    )
    db_session.add(imp)
    db_session.flush()
    return imp


def test_delete_import_without_published_assets(client, seeded_kb, db_session):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    db_session.add(
        Document(
            kb_id=seeded_kb.kb_id,
            import_id=imp.import_id,
            source_type=DocumentSourceType.actual_bid,
            document_name="del-test.docx",
            created_by="tester",
        )
    )
    db_session.commit()

    resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "deleted"
    db_session.expire_all()
    assert db_session.get(FileImport, imp.import_id).status == FileImportStatus.deleted

    listed = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
        headers={"X-Operator-Id": "tester"},
    )
    ids = [item["import_id"] for item in listed.json()["data"]["items"]]
    assert str(imp.import_id) not in ids


def test_delete_import_with_published_ku_returns_409(client, seeded_kb, db_session):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    db_session.add(
        KnowledgeUnit(
            kb_id=seeded_kb.kb_id,
            title="Published KU",
            content="body",
            knowledge_type="solution",
            product_category_ids=[],
            import_id=imp.import_id,
            candidate_id=uuid4(),
            published_by="tester",
            status=KnowledgeUnitStatus.published,
        )
    )
    db_session.commit()

    resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PUBLISHED_ASSETS_EXIST"
    assert resp.json()["error"]["details"]["published_counts"]["ku"] == 1


def test_delete_import_deprecates_published_ku(client, seeded_kb, db_session):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    ku = KnowledgeUnit(
        kb_id=seeded_kb.kb_id,
        title="Published KU",
        content="body",
        knowledge_type="solution",
        product_category_ids=[],
        import_id=imp.import_id,
        candidate_id=uuid4(),
        published_by="tester",
        status=KnowledgeUnitStatus.published,
    )
    db_session.add(ku)
    db_session.commit()

    resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}?deprecate_published=true",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    db_session.refresh(ku)
    assert ku.status == KnowledgeUnitStatus.deprecated


def test_purge_impact_returns_counts(client, seeded_kb, db_session):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    db_session.commit()

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}/purge-impact",
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["import_id"] == str(imp.import_id)
    assert resp.json()["data"]["has_published_assets"] is False
