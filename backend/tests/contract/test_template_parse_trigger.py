from uuid import uuid4

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import app
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.template_parse_task import TemplateParseTask, TemplateParseTaskStatus


def test_trigger_parse_and_get_task(api_client, db_session, seeded_kb, sample_docx_path):
    client = TestClient(app)
    storage_rel = f"{seeded_kb.kb_id}/sample-template.docx"
    from pathlib import Path

    storage_abs = Path(Settings().storage_root) / storage_rel
    storage_abs.parent.mkdir(parents=True, exist_ok=True)
    storage_abs.write_bytes(sample_docx_path.read_bytes())
    record = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="sample-template.docx",
        file_type=FileType.docx,
        file_size=storage_abs.stat().st_size,
        storage_path=storage_rel,
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.confirmed,
        created_by="admin",
    )
    db_session.add(record)
    db_session.commit()
    import_id = record.import_id

    trigger = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-parse/trigger",
        headers={"X-Operator-Id": "admin"},
        json={"import_id": str(import_id)},
    )
    assert trigger.status_code == 202
    data = trigger.json()["data"]
    assert data["import_id"] == str(import_id)
    assert data["status"] in {"pending", "running", "parse_ready", "failed"}
    parse_task_id = data["parse_task_id"]

    detail = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-parse/tasks/{parse_task_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["parse_task_id"] == parse_task_id
    assert detail_data["import_id"] == str(import_id)


def test_retry_failed_parse_task(api_client, db_session, seeded_kb):
    client = TestClient(app)
    missing = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="missing.docx",
        file_type=FileType.docx,
        file_size=10,
        storage_path="missing/missing.docx",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.confirmed,
        created_by="admin",
    )
    db_session.add(missing)
    db_session.flush()

    task = TemplateParseTask(
        kb_id=seeded_kb.kb_id,
        import_id=missing.import_id,
        status=TemplateParseTaskStatus.failed,
        trace_id=uuid4(),
        error_message="boom",
    )
    db_session.add(task)
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-parse/tasks/{task.parse_task_id}/retry",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 202
    payload = resp.json()["data"]
    assert payload["import_id"] == str(missing.import_id)
    assert payload["status"] in {"pending", "running", "parse_ready", "failed"}
