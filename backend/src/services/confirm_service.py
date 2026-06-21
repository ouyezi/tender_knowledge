from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose
from src.models.import_audit_log import ImportAuditAction, ImportAuditLog
from src.services.document_parse_runner import enqueue_document_parse


class ConfirmServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_import_or_raise(db: Session, kb_id: UUID, import_id: UUID) -> FileImport:
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        raise ConfirmServiceError(
            "File import not found", code="NOT_FOUND", status_code=404
        )
    return record


def _assert_can_change(record: FileImport, expected_version: int) -> None:
    if record.status != FileImportStatus.need_confirm:
        raise ConfirmServiceError(
            "Only need_confirm imports can be updated",
            code="INVALID_STATE",
            status_code=422,
        )
    if record.version != expected_version:
        raise ConfirmServiceError(
            "Version mismatch", code="CONFLICT", status_code=409
        )


def _build_confirm_payload(record: FileImport) -> dict:
    return {
        "import_id": str(record.import_id),
        "status": record.status.value,
        "file_purpose": record.file_purpose.value if record.file_purpose else None,
        "enter_parsing": record.enter_parsing,
        "version": record.version,
        "confirmed_by": record.confirmed_by,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
    }


def _downstream_task_types(file_purpose: FilePurpose, enter_parsing: bool) -> list[DownstreamTaskType]:
    if not enter_parsing:
        return []
    if file_purpose in {FilePurpose.actual_bid, FilePurpose.template_file}:
        return [DownstreamTaskType.document_parse]
    return []


def create_downstream_entries(
    db: Session,
    *,
    record: FileImport,
    operator_id: str,
    trace_id: UUID | None,
) -> list[dict]:
    created: list[dict] = []
    task_types = _downstream_task_types(record.file_purpose, bool(record.enter_parsing))
    if not task_types:
        return created

    existing = (
        db.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.import_id == record.import_id)
        .all()
    )
    existing_types = {item.task_type for item in existing}

    for task_type in task_types:
        if task_type in existing_types:
            continue
        entry = DownstreamTaskEntry(
            kb_id=record.kb_id,
            import_id=record.import_id,
            task_type=task_type,
            status=DownstreamTaskStatus.pending,
            payload={
                "file_purpose": record.file_purpose.value if record.file_purpose else None,
            },
        )
        db.add(entry)
        db.flush()
        created.append(
            {
                "entry_id": str(entry.entry_id),
                "task_type": entry.task_type.value,
                "status": entry.status.value,
            }
        )

    if created:
        db.add(
            ImportAuditLog(
                trace_id=trace_id or uuid4(),
                kb_id=record.kb_id,
                import_id=record.import_id,
                operator_id=operator_id,
                action=ImportAuditAction.route,
                payload_summary={"entries": created},
            )
        )
    return created


def confirm_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    expected_version: int,
    file_purpose: FilePurpose,
    enter_parsing: bool,
    operator_id: str,
    trace_id: UUID | None,
) -> dict:
    record = _get_import_or_raise(db, kb_id, import_id)
    _assert_can_change(record, expected_version)

    if file_purpose not in {FilePurpose.actual_bid, FilePurpose.template_file}:
        raise ConfirmServiceError(
            f"Unsupported file purpose: {file_purpose.value}",
            code="VALIDATION",
            status_code=422,
        )

    record.file_purpose = file_purpose
    record.enter_parsing = enter_parsing
    record.status = FileImportStatus.confirmed
    record.confirmed_by = operator_id
    record.confirmed_at = _now()
    record.version += 1

    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.confirm,
            payload_summary={
                "file_purpose": file_purpose.value,
                "enter_parsing": enter_parsing,
            },
        )
    )
    created_downstream_entries: list[dict] = []
    parse_task_id: str | None = None
    if enter_parsing:
        parse_task = enqueue_document_parse(
            db,
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            trace_id=trace_id,
        )
        parse_task_id = str(parse_task.parse_task_id)
    else:
        created_downstream_entries = create_downstream_entries(
            db,
            record=record,
            operator_id=operator_id,
            trace_id=trace_id,
        )
    db.commit()
    db.refresh(record)
    payload = _build_confirm_payload(record)
    payload["downstream_entries_created"] = created_downstream_entries
    payload["parse_task_id"] = parse_task_id
    return payload


def ignore_import(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    expected_version: int,
    reason: str | None,
    operator_id: str,
    trace_id: UUID | None,
) -> dict:
    record = _get_import_or_raise(db, kb_id, import_id)
    _assert_can_change(record, expected_version)

    record.status = FileImportStatus.ignored
    record.enter_parsing = False
    record.version += 1

    db.add(
        ImportAuditLog(
            trace_id=trace_id or uuid4(),
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            action=ImportAuditAction.ignore,
            payload_summary={"reason": reason or ""},
        )
    )
    db.commit()
    db.refresh(record)
    return {
        "import_id": str(record.import_id),
        "status": record.status.value,
        "enter_parsing": record.enter_parsing,
        "version": record.version,
    }
