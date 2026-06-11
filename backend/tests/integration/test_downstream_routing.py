from src.models.downstream_task_entry import DownstreamTaskEntry
from src.models.file_import import FileImport


def _confirm(client, kb_id, import_id, expected_version: int, file_purpose: str, enter_parsing: bool):
    return client.post(
        f"/api/v1/kbs/{kb_id}/file-imports/{import_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "expected_version": expected_version,
            "file_purpose": file_purpose,
            "product_category_ids": [],
            "enter_parsing": enter_parsing,
        },
    )


def test_template_file_confirm_creates_template_parse_entry(
    client, db_session, uploaded_need_confirm
):
    kb_id = uploaded_need_confirm["kb_id"]
    import_id = uploaded_need_confirm["import_id"]
    record = db_session.get(FileImport, import_id)
    assert record is not None

    resp = _confirm(
        client,
        kb_id,
        import_id,
        expected_version=record.version,
        file_purpose="template_file",
        enter_parsing=True,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    created = data["downstream_entries_created"]
    assert len(created) == 1
    assert created[0]["task_type"] == "template_file_parse"
    assert created[0]["status"] == "pending"


def test_actual_bid_confirm_creates_three_entries(client, db_session, uploaded_need_confirm):
    kb_id = uploaded_need_confirm["kb_id"]
    import_id = uploaded_need_confirm["import_id"]
    record = db_session.get(FileImport, import_id)
    assert record is not None

    resp = _confirm(
        client,
        kb_id,
        import_id,
        expected_version=record.version,
        file_purpose="actual_bid",
        enter_parsing=True,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    task_types = {item["task_type"] for item in data["downstream_entries_created"]}
    assert task_types == {
        "document_parse",
        "bid_outline_extract",
        "candidate_knowledge_generate",
    }


def test_confirm_with_enter_parsing_false_creates_no_entries(
    client, db_session, uploaded_need_confirm
):
    kb_id = uploaded_need_confirm["kb_id"]
    import_id = uploaded_need_confirm["import_id"]
    record = db_session.get(FileImport, import_id)
    assert record is not None

    resp = _confirm(
        client,
        kb_id,
        import_id,
        expected_version=record.version,
        file_purpose="template_file",
        enter_parsing=False,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["downstream_entries_created"] == []

    db_entries = (
        db_session.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.import_id == import_id)
        .all()
    )
    assert db_entries == []
