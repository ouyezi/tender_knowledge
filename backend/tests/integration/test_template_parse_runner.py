from pathlib import Path

from src.config import Settings
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.template import Template, TemplateStatus
from src.models.template_audit_log import TemplateAuditAction, TemplateAuditLog
from src.models.template_parse_suggestion import TemplateParseSuggestion
from src.models.template_parse_task import TemplateParseTask, TemplateParseTaskStatus
from src.services.template_parse_runner import run_template_parse_pending


def _seed_confirmed_import_with_downstream(db_session, seeded_kb, sample_docx_path):
    storage_rel = f"{seeded_kb.kb_id}/sample-template.docx"
    storage_abs = Path(Settings().storage_root) / storage_rel
    storage_abs.parent.mkdir(parents=True, exist_ok=True)
    storage_abs.write_bytes(sample_docx_path.read_bytes())

    record = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="sample-template.docx",
        file_type=FileType.docx,
        file_size=storage_abs.stat().st_size,
        storage_path=storage_rel,
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.template_file,
        created_by="admin",
    )
    db_session.add(record)
    db_session.flush()
    db_session.add(
        DownstreamTaskEntry(
            kb_id=seeded_kb.kb_id,
            import_id=record.import_id,
            task_type=DownstreamTaskType.template_file_parse,
            status=DownstreamTaskStatus.pending,
        )
    )
    db_session.commit()
    return record.import_id


def test_template_parse_runner_creates_parse_outputs(db_session, seeded_kb, sample_docx_path):
    import_id = _seed_confirmed_import_with_downstream(db_session, seeded_kb, sample_docx_path)

    run_template_parse_pending(db_session)

    task = (
        db_session.query(TemplateParseTask)
        .filter(TemplateParseTask.import_id == import_id)
        .order_by(TemplateParseTask.created_at.desc())
        .first()
    )
    assert task is not None
    assert task.status == TemplateParseTaskStatus.parse_ready
    assert task.template_id is not None

    tpl = db_session.get(Template, task.template_id)
    assert tpl is not None
    assert tpl.source_import_id == import_id
    assert tpl.status == TemplateStatus.draft

    suggestion = (
        db_session.query(TemplateParseSuggestion)
        .filter(TemplateParseSuggestion.parse_task_id == task.parse_task_id)
        .one_or_none()
    )
    assert suggestion is not None
    assert isinstance(suggestion.suggested_chapter_tree, list)

    downstream = (
        db_session.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.import_id == import_id)
        .one()
    )
    assert downstream.status == DownstreamTaskStatus.completed

    audit = (
        db_session.query(TemplateAuditLog)
        .filter(
            TemplateAuditLog.import_id == import_id,
            TemplateAuditLog.action == TemplateAuditAction.parse_complete,
        )
        .one_or_none()
    )
    assert audit is not None


def test_template_parse_runner_populates_llm_progress_and_block_classification(
    db_session, seeded_kb, sample_docx_path, monkeypatch
):
    from src.config import settings

    monkeypatch.setattr(settings, "llm_api_key", None)

    import_id = _seed_confirmed_import_with_downstream(db_session, seeded_kb, sample_docx_path)
    run_template_parse_pending(db_session)

    task = (
        db_session.query(TemplateParseTask)
        .filter(TemplateParseTask.import_id == import_id)
        .one()
    )
    assert task.llm_progress is not None
    assert task.llm_progress["total_chunks"] >= 1
    assert task.llm_progress["completed_chunks"] == task.llm_progress["total_chunks"]

    suggestion = (
        db_session.query(TemplateParseSuggestion)
        .filter(TemplateParseSuggestion.parse_task_id == task.parse_task_id)
        .one()
    )
    assert suggestion.suggested_product_category_ids == []
    first_chapter = suggestion.suggested_chapter_tree[0]
    assert "suggestion_source" in first_chapter
    assert "classification_confidence" in first_chapter


def test_template_parse_runner_marks_failed_when_source_missing(db_session, seeded_kb):
    missing = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="missing.docx",
        file_type=FileType.docx,
        file_size=123,
        storage_path="not-exist/missing.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.template_file,
        created_by="admin",
    )
    db_session.add(missing)
    db_session.flush()
    downstream = DownstreamTaskEntry(
        kb_id=seeded_kb.kb_id,
        import_id=missing.import_id,
        task_type=DownstreamTaskType.template_file_parse,
        status=DownstreamTaskStatus.pending,
    )
    db_session.add(downstream)
    db_session.commit()

    run_template_parse_pending(db_session)

    task = (
        db_session.query(TemplateParseTask)
        .filter(TemplateParseTask.import_id == missing.import_id)
        .one_or_none()
    )
    assert task is not None
    assert task.status == TemplateParseTaskStatus.failed
    assert task.error_message

    db_session.refresh(downstream)
    assert downstream.status == DownstreamTaskStatus.failed

    audit = (
        db_session.query(TemplateAuditLog)
        .filter(
            TemplateAuditLog.import_id == missing.import_id,
            TemplateAuditLog.action == TemplateAuditAction.parse_fail,
        )
        .one_or_none()
    )
    assert audit is not None
