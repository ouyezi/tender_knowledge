from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import app
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.template import Template, TemplateType
from src.models.template_chapter import TemplateChapter
from src.models.template_parse_task import TemplateParseTask
from src.models.template_structure_diff import TemplateStructureDiff, TemplateStructureDiffStatus
from src.services.template_parse_runner import run_template_parse_pending


def _seed_locked_template_parse(db_session, seeded_kb, sample_docx_path):
    storage_rel = f"{seeded_kb.kb_id}/locked-template.docx"
    storage_abs = Path(Settings().storage_root) / storage_rel
    storage_abs.parent.mkdir(parents=True, exist_ok=True)
    storage_abs.write_bytes(sample_docx_path.read_bytes())

    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="locked-template.docx",
        file_type=FileType.docx,
        file_size=storage_abs.stat().st_size,
        storage_path=storage_rel,
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.template_file,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=file_import.import_id,
        template_name="已锁定模板",
        template_type=TemplateType.technical_bid,
        confirmed=True,
        structure_locked_by="admin",
        structure_locked_at=file_import.created_at,
        created_by="admin",
    )
    db_session.add(template)
    db_session.flush()
    db_session.add(
        TemplateChapter(
            kb_id=seeded_kb.kb_id,
            template_id=template.template_id,
            title="旧章节",
            level=1,
            sort_order=0,
            parse_source_ref="old-1",
        )
    )
    db_session.add(
        DownstreamTaskEntry(
            kb_id=seeded_kb.kb_id,
            import_id=file_import.import_id,
            task_type=DownstreamTaskType.template_file_parse,
            status=DownstreamTaskStatus.pending,
            payload={"trace_id": str(uuid4())},
        )
    )
    db_session.commit()
    return template


def test_reparse_locked_template_generates_pending_diff(db_session, seeded_kb, sample_docx_path):
    template = _seed_locked_template_parse(db_session, seeded_kb, sample_docx_path)
    original_count = (
        db_session.query(TemplateChapter)
        .filter(TemplateChapter.template_id == template.template_id)
        .count()
    )

    run_template_parse_pending(db_session)

    diff = (
        db_session.query(TemplateStructureDiff)
        .filter(TemplateStructureDiff.template_id == template.template_id)
        .order_by(TemplateStructureDiff.created_at.desc())
        .first()
    )
    assert diff is not None
    assert diff.status == TemplateStructureDiffStatus.pending_review
    assert isinstance((diff.diff_payload or {}).get("suggested_tree"), list)
    count_after = (
        db_session.query(TemplateChapter)
        .filter(TemplateChapter.template_id == template.template_id)
        .count()
    )
    assert count_after == original_count


def test_diff_apply_and_reject_endpoints(api_client, db_session, seeded_kb, sample_docx_path):
    client = TestClient(app)
    template = _seed_locked_template_parse(db_session, seeded_kb, sample_docx_path)
    run_template_parse_pending(db_session)
    task = (
        db_session.query(TemplateParseTask)
        .filter(TemplateParseTask.template_id == template.template_id)
        .order_by(TemplateParseTask.created_at.desc())
        .first()
    )
    assert task is not None
    diff = (
        db_session.query(TemplateStructureDiff)
        .filter(TemplateStructureDiff.parse_task_id == task.parse_task_id)
        .one()
    )

    get_task_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-parse/tasks/{task.parse_task_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert get_task_resp.status_code == 200
    assert get_task_resp.json()["data"]["structure_diff"]["status"] == "pending_review"

    apply_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-parse/tasks/{task.parse_task_id}/diff/apply",
        headers={"X-Operator-Id": "admin"},
        json={"diff_id": str(diff.diff_id)},
    )
    assert apply_resp.status_code == 200
    assert apply_resp.json()["data"]["structure_diff"]["status"] == "applied"

    # Seed a second parse for reject path
    file_import = db_session.get(FileImport, task.import_id)
    db_session.add(
        DownstreamTaskEntry(
            kb_id=seeded_kb.kb_id,
            import_id=file_import.import_id,
            task_type=DownstreamTaskType.template_file_parse,
            status=DownstreamTaskStatus.pending,
        )
    )
    db_session.commit()
    run_template_parse_pending(db_session)
    new_task = (
        db_session.query(TemplateParseTask)
        .filter(TemplateParseTask.template_id == template.template_id)
        .order_by(TemplateParseTask.created_at.desc())
        .first()
    )
    new_diff = (
        db_session.query(TemplateStructureDiff)
        .filter(
            TemplateStructureDiff.parse_task_id == new_task.parse_task_id,
            TemplateStructureDiff.status == TemplateStructureDiffStatus.pending_review,
        )
        .one()
    )
    reject_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/template-parse/tasks/{new_task.parse_task_id}/diff/reject",
        headers={"X-Operator-Id": "admin"},
        json={"diff_id": str(new_diff.diff_id)},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["data"]["structure_diff"]["status"] == "rejected"
