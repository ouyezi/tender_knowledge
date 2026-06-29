from src.models.file_import import FileImportStatus, FilePurpose, FileType
from src.services.file_import_purge_service import purge_file_import


def test_delete_file_import_returns_deleted_counts(client, seeded_kb, db_session):
    from tests.conftest import _seed_file_import

    imp = _seed_file_import(db_session, seeded_kb.kb_id, name="delete-me.docx")
    db_session.commit()

    resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{imp.import_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "deleted"
    assert body["deleted_counts"]["file_imports"] >= 1

    listed = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports")
    assert listed.status_code == 200
    assert all(item["import_id"] != str(imp.import_id) for item in listed.json()["data"]["items"])


def test_purge_impact_returns_knowledge_chunk_counts(client, seeded_kb, db_session):
    from uuid import uuid4

    from src.models.document import Document, DocumentParseStatus, DocumentSourceType
    from src.models.file_import import FileImport
    from src.models.knowledge_chunk import KnowledgeChunk

    import_id = uuid4()
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="impact.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/impact.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        created_by="admin",
    )
    db_session.add(imp)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="impact.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(doc)
    db_session.flush()
    db_session.add(
        KnowledgeChunk(
            id=1,
            kb_id=seeded_kb.kb_id,
            knowledge_code="K-002",
            version="1.0",
            title="t",
            content="c",
            knowledge_type="fact",
            doc_id=doc.document_id,
            catalog_path=[],
            primary_node_id=str(uuid4()),
            block_type_code="product_solution",
            application_type_code="preferred_reference",
            business_line_codes=["general"],
            tags=[],
            regions=[],
            content_hash="abc123",
            token_count=1,
        )
    )
    db_session.commit()

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{import_id}/purge-impact",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    counts = resp.json()["data"]["intermediate_counts"]
    assert counts["knowledge_chunks"] >= 1
