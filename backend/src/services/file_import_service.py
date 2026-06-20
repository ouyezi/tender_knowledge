from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from src.models.file_import import (
    DuplicateResolution,
    FileImport,
    FileImportStatus,
    FileType,
    HashStatus,
)
from src.models.file_purpose_suggestion import FilePurposeSuggestion
from src.models.file_purpose_suggestion import SuggestionSource
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.services.duplicate_detection import find_duplicates_by_hash
from src.services.file_hash import sha256_stream
from src.services.file_storage import FileStorage
from src.services.import_task_runner import run_post_upload

ALLOWED_EXTENSIONS: dict[str, FileType] = {
    ".docx": FileType.docx,
    ".docm": FileType.docx,
    ".pdf": FileType.pdf,
    ".ppt": FileType.ppt,
    ".pptx": FileType.ppt,
    ".xlsx": FileType.xlsx,
    ".png": FileType.image,
    ".jpg": FileType.image,
    ".jpeg": FileType.image,
    ".bmp": FileType.image,
    ".webp": FileType.image,
}


def _iter_upload_chunks(upload_file: UploadFile, chunk_size: int = 1024 * 1024):
    while True:
        chunk = upload_file.file.read(chunk_size)
        if not chunk:
            break
        yield chunk


class FileImportServiceError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        details: dict | None = None,
    ):
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _suggest_from_filename(file_name: str, file_type: str):
    lower_name = file_name.lower()
    if "模板" in lower_name or "template" in lower_name:
        purpose = FilePurpose.template_file
        rationale = "文件名命中模板关键词"
    else:
        purpose = FilePurpose.actual_bid
        rationale = "默认归类为投标文件"
    return {
        "suggested_purpose": purpose,
        "purpose_confidence": 0.6,
        "suggestion_source": SuggestionSource.rule,
        "rationale": f"{rationale} (type={file_type})",
    }


def upload_file_and_enqueue(
    db: Session,
    *,
    kb_id: UUID,
    operator_id: str,
    upload_file: UploadFile,
    background_tasks: BackgroundTasks,
    duplicate_action: DuplicateResolution = DuplicateResolution.normal,
    parent_import_id: UUID | None = None,
) -> FileImport:
    filename = upload_file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise FileImportServiceError(
            "unsupported file extension",
            code="VALIDATION",
            status_code=422,
            details={"extension": suffix or None},
        )

    import_id = uuid4()
    storage = FileStorage()
    rel_path = storage.save(
        kb_id=kb_id,
        import_id=import_id,
        file_name=filename,
        stream=_iter_upload_chunks(upload_file),
    )
    abs_path = storage.root / rel_path
    file_size = abs_path.stat().st_size
    if file_size <= 0:
        abs_path.unlink(missing_ok=True)
        raise FileImportServiceError(
            "zero-byte file is not allowed",
            code="VALIDATION",
            status_code=422,
        )

    is_duplicate_new_version = False
    rec = FileImport(
        import_id=import_id,
        kb_id=kb_id,
        file_name=filename,
        file_type=ALLOWED_EXTENSIONS[suffix],
        file_size=file_size,
        file_hash=None,
        hash_status=HashStatus.computed,
        storage_path=rel_path,
        status=FileImportStatus.uploaded,
        created_by=operator_id,
        duplicate_resolution=duplicate_action,
    )
    file_hash = sha256_stream(abs_path)
    rec.file_hash = file_hash
    duplicates = find_duplicates_by_hash(
        db,
        kb_id=kb_id,
        file_hash=file_hash,
    )
    if duplicates:
        existing = duplicates[0]
        if duplicate_action == DuplicateResolution.skip:
            db.add(
                ImportAuditLog(
                    trace_id=uuid4(),
                    kb_id=kb_id,
                    import_id=existing.import_id,
                    operator_id=operator_id,
                    action=ImportAuditAction.duplicate_skip,
                    payload_summary={
                        "existing_import_id": str(existing.import_id),
                        "file_hash": file_hash,
                    },
                )
            )
            db.commit()
            return existing
        if duplicate_action == DuplicateResolution.normal:
            abs_path.unlink(missing_ok=True)
            raise FileImportServiceError(
                "相同内容的文件已导入",
                code="DUPLICATE_FILE",
                status_code=409,
                details={
                    "existing_import_ids": [str(item.import_id) for item in duplicates],
                    "file_hash": file_hash,
                },
            )
        resolved_parent_id = parent_import_id or existing.import_id
        parent = db.get(FileImport, resolved_parent_id)
        if parent is None or parent.kb_id != kb_id:
            abs_path.unlink(missing_ok=True)
            raise FileImportServiceError(
                "parent_import_id not found",
                code="VALIDATION",
                status_code=422,
            )
        rec.parent_import_id = resolved_parent_id
        rec.version_no = max(parent.version_no + 1, 2)
        rec.file_hash = None
        rec.hash_status = HashStatus.unavailable
        rec.status = FileImportStatus.need_confirm
        is_duplicate_new_version = True
        suggestion = _suggest_from_filename(rec.file_name, rec.file_type.value)
        db.add(
            FilePurposeSuggestion(
                kb_id=kb_id,
                import_id=rec.import_id,
                suggested_purpose=suggestion["suggested_purpose"],
                purpose_confidence=suggestion["purpose_confidence"],
                suggestion_source=suggestion["suggestion_source"],
                rationale=suggestion["rationale"],
            )
        )
        db.add(
            ImportAuditLog(
                trace_id=uuid4(),
                kb_id=kb_id,
                import_id=parent.import_id,
                operator_id=operator_id,
                action=ImportAuditAction.duplicate_new_version,
                payload_summary={
                    "new_import_id": str(rec.import_id),
                    "duplicate_of": str(parent.import_id),
                    "file_hash": file_hash,
                },
            )
        )
        db.add(
            ImportAuditLog(
                trace_id=uuid4(),
                kb_id=kb_id,
                import_id=rec.import_id,
                operator_id=operator_id,
                action=ImportAuditAction.suggest_ready,
                payload_summary={"suggested_purpose": suggestion["suggested_purpose"].value},
            )
        )

    db.add(rec)
    db.commit()
    db.refresh(rec)

    if not is_duplicate_new_version:
        background_tasks.add_task(_run_post_upload_in_new_session, rec.import_id)
    return rec


def _run_post_upload_in_new_session(import_id: UUID) -> None:
    from src.db.session import SessionLocal

    db = SessionLocal()
    try:
        run_post_upload(db, import_id)
    finally:
        db.close()
