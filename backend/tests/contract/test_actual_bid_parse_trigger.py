from pathlib import Path

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import app
from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType


def _seed_confirmed_actual_bid_import(db_session, seeded_kb, sample_docx_path):
    storage_rel = f"{seeded_kb.kb_id}/sample-actual-bid.docx"
    storage_abs = Path(Settings().storage_root) / storage_rel
    storage_abs.parent.mkdir(parents=True, exist_ok=True)
    storage_abs.write_bytes(sample_docx_path.read_bytes())
    record = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="sample-actual-bid.docx",
        file_type=FileType.docx,
        file_size=storage_abs.stat().st_size,
        storage_path=storage_rel,
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def test_trigger_parse_and_get_task(api_client, db_session, seeded_kb, sample_docx_path):
    client = TestClient(app)
    record = _seed_confirmed_actual_bid_import(db_session, seeded_kb, sample_docx_path)

    trigger = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/actual-bid-parse/trigger",
        headers={"X-Operator-Id": "admin"},
        json={"import_id": str(record.import_id), "force_reparse": False},
    )
    assert trigger.status_code == 202
    data = trigger.json()["data"]
    assert data["import_id"] == str(record.import_id)
    assert data["status"] in {"pending", "running", "ready", "failed"}
    parse_task_id = data["parse_task_id"]

    detail = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/actual-bid-parse/tasks/{parse_task_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["parse_task_id"] == parse_task_id
    assert detail_data["import_id"] == str(record.import_id)

    task_list = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/actual-bid-parse/tasks",
        headers={"X-Operator-Id": "admin"},
    )
    assert task_list.status_code == 200
    items = task_list.json()["data"]["items"]
    assert any(item["parse_task_id"] == parse_task_id for item in items)


def test_confirm_actual_bid_auto_enqueues_parse(client, db_session, uploaded_need_confirm):
    kb_id = uploaded_need_confirm["kb_id"]
    import_id = uploaded_need_confirm["import_id"]
    record = db_session.get(FileImport, import_id)
    assert record is not None

    resp = client.post(
        f"/api/v1/kbs/{kb_id}/file-imports/{import_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "expected_version": record.version,
            "file_purpose": "actual_bid",
            "product_category_ids": [],
            "enter_parsing": True,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["actual_bid_parse_task_id"] is not None

    parse_task = (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == import_id)
        .order_by(ActualBidParseTask.created_at.desc())
        .first()
    )
    assert parse_task is not None
    assert parse_task.status in {
        ActualBidParseTaskStatus.pending,
        ActualBidParseTaskStatus.running,
        ActualBidParseTaskStatus.ready,
        ActualBidParseTaskStatus.failed,
    }


def test_list_file_imports_maps_actual_bid_parse_status(client, db_session, seeded_kb, sample_docx_path):
    status_expectations = {
        ActualBidParseTaskStatus.pending: "parsing",
        ActualBidParseTaskStatus.running: "parsing",
        ActualBidParseTaskStatus.ready: "parse_ready",
        ActualBidParseTaskStatus.confirmed: "parse_confirmed",
        ActualBidParseTaskStatus.failed: "parse_failed",
    }

    import_ids_by_status = {}
    for task_status in status_expectations:
        record = _seed_confirmed_actual_bid_import(db_session, seeded_kb, sample_docx_path)
        db_session.add(
            ActualBidParseTask(
                kb_id=seeded_kb.kb_id,
                import_id=record.import_id,
                status=task_status,
                created_by="admin",
            )
        )
        db_session.flush()
        import_ids_by_status[record.import_id] = status_expectations[task_status]
    db_session.commit()

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    parse_status_by_import = {
        item["import_id"]: item["parse_status"] for item in items if item["file_purpose"] == "actual_bid"
    }
    for import_id, expected_status in import_ids_by_status.items():
        assert parse_status_by_import[str(import_id)] == expected_status
