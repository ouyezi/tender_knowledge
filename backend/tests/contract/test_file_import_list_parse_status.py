from fastapi.testclient import TestClient

from src.main import app
from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.models.knowledge_base import KBStatus, KnowledgeBase


def test_list_file_imports_maps_ready_parse_task(api_client, db_session):
    kb = KnowledgeBase(name="test-kb", status=KBStatus.active)
    db_session.add(kb)
    db_session.flush()

    file_import = FileImport(
        kb_id=kb.kb_id,
        file_name="餐补标书.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path=f"{kb.kb_id}/imports/sample.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(file_import)
    db_session.flush()

    db_session.add(
        ActualBidParseTask(
            kb_id=kb.kb_id,
            import_id=file_import.import_id,
            status=ActualBidParseTaskStatus.ready,
            created_by="tester",
        )
    )
    db_session.commit()

    client = TestClient(app)
    response = client.get(
        f"/api/v1/kbs/{kb.kb_id}/file-imports",
        headers={"X-Operator-Id": "admin"},
    )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["parse_status"] == "parse_ready"
