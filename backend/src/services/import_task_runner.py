from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import Settings
from src.models.file_import import FileImport, FileImportStatus, HashStatus
from src.models.file_purpose_suggestion import FilePurposeSuggestion
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.models.import_task import ImportTask, ImportTaskStatus, ImportTaskType
from src.services.file_hash import sha256_stream


class _SuggestionPayload:
    def __init__(self, suggested_purpose, purpose_confidence, suggestion_source, rationale):
        self.suggested_purpose = suggested_purpose
        self.purpose_confidence = purpose_confidence
        self.suggestion_source = suggestion_source
        self.rationale = rationale


def _suggest_from_filename(file_import: FileImport) -> _SuggestionPayload:
    from src.models.file_import import FilePurpose
    from src.models.file_purpose_suggestion import SuggestionSource

    lower_name = file_import.file_name.lower()
    if "模板" in lower_name or "template" in lower_name:
        purpose = FilePurpose.template_file
        rationale = "文件名命中模板关键词"
    else:
        purpose = FilePurpose.actual_bid
        rationale = "默认归类为投标文件"
    return _SuggestionPayload(
        suggested_purpose=purpose,
        purpose_confidence=0.6,
        suggestion_source=SuggestionSource.rule,
        rationale=f"{rationale} (type={file_import.file_type.value})",
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_task(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    task_type: ImportTaskType,
    start_message: str,
) -> ImportTask:
    task = ImportTask(
        kb_id=kb_id,
        import_id=import_id,
        task_type=task_type,
        status=ImportTaskStatus.running,
        started_at=_now(),
        log_lines=[{"ts": _now().isoformat(), "level": "info", "message": start_message}],
    )
    db.add(task)
    db.flush()
    return task


def _finish_task(task: ImportTask, message: str, *, failed: bool = False) -> None:
    task.status = ImportTaskStatus.failed if failed else ImportTaskStatus.completed
    task.finished_at = _now()
    lines = list(task.log_lines or [])
    lines.append(
        {
            "ts": _now().isoformat(),
            "level": "error" if failed else "info",
            "message": message,
        }
    )
    task.log_lines = lines


def run_post_upload(db: Session, import_id: UUID) -> None:
    file_import = db.get(FileImport, import_id)
    if file_import is None:
        return

    hash_task = _new_task(
        db,
        kb_id=file_import.kb_id,
        import_id=file_import.import_id,
        task_type=ImportTaskType.file_import,
        start_message="开始计算文件哈希",
    )
    classify_task = _new_task(
        db,
        kb_id=file_import.kb_id,
        import_id=file_import.import_id,
        task_type=ImportTaskType.file_purpose_classify,
        start_message="开始生成用途建议",
    )
    db.flush()

    cfg = Settings()
    abs_path = cfg.storage_root + "/" + file_import.storage_path
    try:
        file_hash = sha256_stream(abs_path)
        file_import.file_hash = file_hash
        file_import.hash_status = HashStatus.computed
        _finish_task(hash_task, "文件哈希计算完成")

        suggestion = _suggest_from_filename(file_import)
        exists = (
            db.query(FilePurposeSuggestion)
            .filter(FilePurposeSuggestion.import_id == file_import.import_id)
            .one_or_none()
        )
        if exists is None:
            exists = FilePurposeSuggestion(
                import_id=file_import.import_id,
                kb_id=file_import.kb_id,
            )
            db.add(exists)
        exists.suggested_purpose = suggestion.suggested_purpose
        exists.purpose_confidence = suggestion.purpose_confidence
        exists.suggestion_source = suggestion.suggestion_source
        exists.rationale = suggestion.rationale

        file_import.status = FileImportStatus.need_confirm
        _finish_task(classify_task, "用途建议生成完成")
        db.commit()
    except Exception as exc:
        file_import.hash_status = HashStatus.failed
        file_import.status = FileImportStatus.failed
        hash_task.error_message = str(exc)
        classify_task.error_message = str(exc)
        _finish_task(hash_task, f"处理失败: {exc}", failed=True)
        _finish_task(classify_task, f"处理失败: {exc}", failed=True)
        db.commit()


def retry_import_tasks(
    db: Session,
    *,
    import_id: UUID,
    operator_id: str,
    scope: str = "all",
) -> dict:
    file_import = db.get(FileImport, import_id)
    if file_import is None:
        return {"import_id": str(import_id), "status": "not_found", "tasks_enqueued": []}

    tasks_enqueued: list[str] = []
    if scope in {"all", "classify"} and file_import.status in {
        FileImportStatus.failed,
        FileImportStatus.uploaded,
    }:
        run_post_upload(db, import_id)
        tasks_enqueued.append("file_purpose_classify")
    db.add(
        ImportAuditLog(
            trace_id=file_import.import_id,
            kb_id=file_import.kb_id,
            import_id=file_import.import_id,
            operator_id=operator_id,
            action=ImportAuditAction.retry,
            payload_summary={"scope": scope, "tasks_enqueued": tasks_enqueued},
        )
    )
    db.commit()
    db.refresh(file_import)
    return {
        "import_id": str(file_import.import_id),
        "status": file_import.status.value,
        "tasks_enqueued": tasks_enqueued,
    }
