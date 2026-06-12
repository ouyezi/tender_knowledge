from uuid import UUID

from src.models.file_import import (
    DuplicateResolution,
    FileImport,
    FileImportStatus,
    HashStatus,
)
from src.services.import_task_runner import run_post_upload


def test_upload_file_creates_file_import(client, seeded_kb, sample_docx_path, db_session):
    with sample_docx_path.open("rb") as f:
        resp = client.post(
            f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={
                "file": (
                    "餐补模板.docx",
                    f,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "uploaded"
    assert data["file_type"] == "docx"
    assert data["file_name"] == "餐补模板.docx"
    assert data["file_size"] > 0

    imp = db_session.get(FileImport, UUID(data["import_id"]))
    assert imp is not None
    assert imp.status == FileImportStatus.uploaded
    assert imp.hash_status == HashStatus.computed
    assert imp.file_hash is not None
    assert imp.created_by == "admin"


def test_upload_file_rejects_zero_byte_file(client, seeded_kb):
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
        headers={"X-Operator-Id": "admin"},
        files={"file": ("empty.docx", b"", "application/octet-stream")},
    )
    assert resp.status_code == 422


def test_upload_docm_maps_to_docx_type(client, seeded_kb, sample_docx_path):
    with sample_docx_path.open("rb") as f:
        resp = client.post(
            f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={
                "file": (
                    "鼎信餐补标书.docm",
                    f,
                    "application/vnd.ms-word.document.macroenabled.12",
                )
            },
        )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["file_type"] == "docx"
    assert data["file_name"] == "鼎信餐补标书.docm"


def test_upload_file_rejects_bad_extension(client, seeded_kb):
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
        headers={"X-Operator-Id": "admin"},
        files={"file": ("bad.exe", b"abc", "application/octet-stream")},
    )
    assert resp.status_code == 422


def test_get_file_import_detail_with_suggestion_after_runner(
    client, seeded_kb, sample_docx_path, db_session
):
    with sample_docx_path.open("rb") as f:
        upload = client.post(
            f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={"file": ("餐补模板.docx", f, "application/octet-stream")},
        )
    assert upload.status_code == 201
    import_id = upload.json()["data"]["import_id"]

    run_post_upload(db_session, UUID(import_id))

    detail = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports/{import_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["status"] == "need_confirm"
    assert body["suggestion"] is not None
    assert body["suggestion"]["suggested_purpose"] == "template_file"


def test_upload_duplicate_returns_409(client, seeded_kb, sample_docx_path):
    with sample_docx_path.open("rb") as f:
        first = client.post(
            f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={"file": ("餐补模板.docx", f, "application/octet-stream")},
        )
    assert first.status_code == 201

    with sample_docx_path.open("rb") as f:
        second = client.post(
            f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={"file": ("餐补模板-重复.docx", f, "application/octet-stream")},
        )

    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "DUPLICATE_FILE"
    assert body["error"]["details"]["existing_import_ids"]
    assert body["error"]["details"]["file_hash"]


def test_upload_duplicate_new_version_creates_child(
    client, seeded_kb, sample_docx_path, db_session
):
    with sample_docx_path.open("rb") as f:
        first = client.post(
            f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={"file": ("餐补模板.docx", f, "application/octet-stream")},
        )
    assert first.status_code == 201
    first_id = UUID(first.json()["data"]["import_id"])

    with sample_docx_path.open("rb") as f:
        second = client.post(
            f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={
                "file": ("餐补模板-新版本.docx", f, "application/octet-stream"),
                "duplicate_action": (None, "new_version"),
                "parent_import_id": (None, str(first_id)),
            },
        )
    assert second.status_code == 201
    second_id = UUID(second.json()["data"]["import_id"])
    assert second_id != first_id

    second_rec = db_session.get(FileImport, second_id)
    assert second_rec is not None
    assert second_rec.parent_import_id == first_id
    assert second_rec.version_no == 2
    assert second_rec.duplicate_resolution == DuplicateResolution.new_version
