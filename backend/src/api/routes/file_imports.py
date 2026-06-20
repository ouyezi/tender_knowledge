from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.file_import import FileImport
from src.models.file_import import (
    DuplicateResolution,
    FileImportStatus,
    FilePurpose,
)
from src.models.file_purpose_suggestion import FilePurposeSuggestion
from src.models.downstream_task_entry import DownstreamTaskEntry
from src.models.import_task import ImportTask
from src.models.knowledge_base import KnowledgeBase
from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.services.confirm_service import (
    ConfirmServiceError,
    confirm_import,
    create_downstream_entries,
    ignore_import,
)
from src.services.file_import_service import FileImportServiceError, upload_file_and_enqueue
from src.services.file_import_purge_service import (
    FileImportPurgeServiceError,
    check_purge_impact,
    purge_all_file_imports,
    purge_file_import,
)
from src.services.import_task_runner import retry_import_tasks
from src.services.document_parse_runner import (
    DocumentParseServiceError,
    enqueue_document_parse,
    run_document_parse_in_new_session,
)
from src.models.import_audit_log import ImportAuditLog

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/file-imports",
    tags=["file-imports"],
)


class ConfirmImportRequest(BaseModel):
    expected_version: int
    file_purpose: FilePurpose
    enter_parsing: bool = True


class IgnoreImportRequest(BaseModel):
    expected_version: int
    reason: str | None = None


class RetryImportRequest(BaseModel):
    scope: str = "all"


class PurgeAllImportsRequest(BaseModel):
    confirm: bool = False


@router.get("")
def list_file_imports(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(FileImport).filter(
        FileImport.kb_id == kb_id,
        FileImport.status != FileImportStatus.deleted,
    )
    total = q.count()
    rows = (
        q.order_by(FileImport.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    parse_tasks_by_import: dict[str, ActualBidParseTask] = {}
    if rows:
        import_ids = [row.import_id for row in rows]
        parse_tasks = (
            db.query(ActualBidParseTask)
            .filter(ActualBidParseTask.import_id.in_(import_ids))
            .order_by(ActualBidParseTask.import_id.asc(), ActualBidParseTask.created_at.desc())
            .all()
        )
        for task in parse_tasks:
            key = str(task.import_id)
            if key not in parse_tasks_by_import:
                parse_tasks_by_import[key] = task

    def _parse_status(task: ActualBidParseTask | None, import_status: FileImportStatus) -> str | None:
        if task is None:
            if import_status == FileImportStatus.completed:
                return "parse_confirmed"
            if import_status == FileImportStatus.failed:
                return "failed"
            if import_status in {FileImportStatus.confirmed, FileImportStatus.processing}:
                return "parsing"
            return None
        if task.status == ActualBidParseTaskStatus.running:
            return "parsing"
        if task.status == ActualBidParseTaskStatus.completed:
            return "parse_confirmed"
        if task.status == ActualBidParseTaskStatus.failed:
            return "failed"
        if task.status == ActualBidParseTaskStatus.pending:
            return "parsing"
        return None

    items = [
        {
            "import_id": str(row.import_id),
            "file_name": row.file_name,
            "file_type": row.file_type.value,
            "file_size": row.file_size,
            "file_hash": row.file_hash,
            "file_purpose": row.file_purpose.value if row.file_purpose else None,
            "status": row.status.value,
            "parse_status": _parse_status(parse_tasks_by_import.get(str(row.import_id)), row.status),
            "latest_parse_task_id": str(parse_tasks_by_import[str(row.import_id)].parse_task_id)
            if str(row.import_id) in parse_tasks_by_import
            else None,
            "document_id": str(parse_tasks_by_import[str(row.import_id)].document_id)
            if str(row.import_id) in parse_tasks_by_import
            and parse_tasks_by_import[str(row.import_id)].document_id
            else None,
            "version_no": row.version_no,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]
    return success(
        {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


@router.post("", status_code=201)
def upload_file_import(
    kb_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    duplicate_action: str = Form("normal"),
    parent_import_id: UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        resolved_action = DuplicateResolution(duplicate_action)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content=error("VALIDATION", "invalid duplicate_action", trace_id=get_trace_id()),
        )
    try:
        rec = upload_file_and_enqueue(
            db,
            kb_id=kb_id,
            operator_id=operator_id,
            upload_file=file,
            background_tasks=background_tasks,
            duplicate_action=resolved_action,
            parent_import_id=parent_import_id,
        )
    except FileImportServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), details=exc.details, trace_id=get_trace_id()),
        )
    return success(
        {
            "import_id": str(rec.import_id),
            "kb_id": str(rec.kb_id),
            "file_name": rec.file_name,
            "file_type": rec.file_type.value,
            "file_size": rec.file_size,
            "status": rec.status.value,
            "version_no": rec.version_no,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
        },
        trace_id=get_trace_id(),
    )


@router.get("/audit-logs")
def list_import_audit_logs(
    kb_id: UUID,
    import_id: UUID | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(ImportAuditLog).filter(ImportAuditLog.kb_id == kb_id)
    if import_id:
        q = q.filter(ImportAuditLog.import_id == import_id)
    total = q.count()
    rows = (
        q.order_by(ImportAuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [
                {
                    "audit_id": str(row.audit_id),
                    "import_id": str(row.import_id) if row.import_id else None,
                    "operator_id": row.operator_id,
                    "action": row.action.value,
                    "payload_summary": row.payload_summary,
                    "trace_id": str(row.trace_id),
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


@router.post("/purge-all")
def purge_all_imports(
    kb_id: UUID,
    body: PurgeAllImportsRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    if not body.confirm:
        return JSONResponse(
            status_code=422,
            content=error(
                "CONFIRM_REQUIRED",
                "Set confirm=true to purge all file imports",
                trace_id=get_trace_id(),
            ),
        )
    try:
        summaries = purge_all_file_imports(
            db,
            kb_id=kb_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
        db.commit()
    except FileImportPurgeServiceError as exc:
        db.rollback()
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    return success(
        {
            "purged_count": len(summaries),
            "items": [
                {
                    "import_id": item.import_id,
                    "file_name": item.file_name,
                    "deleted_counts": item.deleted_counts,
                }
                for item in summaries
            ],
        },
        trace_id=get_trace_id(),
    )


@router.get("/{import_id}")
def get_file_import_detail(
    kb_id: UUID,
    import_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    rec = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="File import not found")

    suggestion = (
        db.query(FilePurposeSuggestion)
        .filter(FilePurposeSuggestion.import_id == import_id)
        .one_or_none()
    )
    suggestion_payload = None
    if rec.status.value == "need_confirm" and suggestion is not None:
        suggestion_payload = {
            "suggested_purpose": suggestion.suggested_purpose.value
            if suggestion.suggested_purpose
            else None,
            "purpose_confidence": suggestion.purpose_confidence,
            "suggested_product_category_ids": suggestion.suggested_product_category_ids,
            "suggested_chapter_taxonomy_id": str(suggestion.suggested_chapter_taxonomy_id)
            if suggestion.suggested_chapter_taxonomy_id
            else None,
            "suggestion_source": suggestion.suggestion_source.value,
            "rationale": suggestion.rationale,
        }

    return success(
        {
            "import_id": str(rec.import_id),
            "kb_id": str(rec.kb_id),
            "file_name": rec.file_name,
            "file_type": rec.file_type.value,
            "file_size": rec.file_size,
            "file_hash": rec.file_hash,
            "hash_status": rec.hash_status.value,
            "storage_path": rec.storage_path,
            "file_purpose": rec.file_purpose.value if rec.file_purpose else None,
            "product_category_ids": rec.product_category_ids,
            "chapter_taxonomy_id": str(rec.chapter_taxonomy_id)
            if rec.chapter_taxonomy_id
            else None,
            "target_object_type": rec.target_object_type.value
            if rec.target_object_type
            else None,
            "enter_parsing": rec.enter_parsing,
            "status": rec.status.value,
            "parent_import_id": str(rec.parent_import_id) if rec.parent_import_id else None,
            "version_no": rec.version_no,
            "version": rec.version,
            "suggestion": suggestion_payload,
            "created_by": rec.created_by,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
            "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
        },
        trace_id=get_trace_id(),
    )


@router.post("/{import_id}/confirm")
def confirm_file_import(
    kb_id: UUID,
    import_id: UUID,
    body: ConfirmImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        data = confirm_import(
            db,
            kb_id=kb_id,
            import_id=import_id,
            expected_version=body.expected_version,
            file_purpose=body.file_purpose,
            enter_parsing=body.enter_parsing,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
    except ConfirmServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    if body.enter_parsing:
        background_tasks.add_task(run_document_parse_in_new_session)
    return success(data, trace_id=get_trace_id())


@router.post("/{import_id}/ignore")
def ignore_file_import(
    kb_id: UUID,
    import_id: UUID,
    body: IgnoreImportRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        data = ignore_import(
            db,
            kb_id=kb_id,
            import_id=import_id,
            expected_version=body.expected_version,
            reason=body.reason,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
    except ConfirmServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    return success(data, trace_id=get_trace_id())


@router.get("/{import_id}/tasks")
def list_import_tasks(
    kb_id: UUID,
    import_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    rows = (
        db.query(ImportTask)
        .filter(ImportTask.kb_id == kb_id, ImportTask.import_id == import_id)
        .order_by(ImportTask.created_at.asc())
        .all()
    )
    return success(
        {
            "items": [
                {
                    "task_id": str(row.task_id),
                    "task_type": row.task_type.value,
                    "status": row.status.value,
                    "retry_count": row.retry_count,
                    "log_lines": row.log_lines or [],
                    "error_message": row.error_message,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                }
                for row in rows
            ]
        },
        trace_id=get_trace_id(),
    )


@router.get("/{import_id}/downstream-entries")
def list_downstream_entries(
    kb_id: UUID,
    import_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    rows = (
        db.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.kb_id == kb_id, DownstreamTaskEntry.import_id == import_id)
        .order_by(DownstreamTaskEntry.created_at.asc())
        .all()
    )
    return success(
        {
            "items": [
                {
                    "entry_id": str(row.entry_id),
                    "task_type": row.task_type.value,
                    "status": row.status.value,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        },
        trace_id=get_trace_id(),
    )


@router.post("/{import_id}/retry")
def retry_import(
    kb_id: UUID,
    import_id: UUID,
    body: RetryImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    record = (
        db.query(FileImport)
        .filter(FileImport.kb_id == kb_id, FileImport.import_id == import_id)
        .one_or_none()
    )
    if record is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "File import not found", trace_id=get_trace_id()),
        )

    tasks_enqueued: list[str] = []
    if body.scope in {"all", "route"} and record.status.value == "confirmed":
        created = create_downstream_entries(
            db,
            record=record,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
        if created:
            db.commit()
        tasks_enqueued.extend([item["task_type"] for item in created])

    retry_data = retry_import_tasks(
        db,
        import_id=import_id,
        operator_id=operator_id,
        scope=body.scope,
    )
    retry_data["tasks_enqueued"] = list(dict.fromkeys(tasks_enqueued + retry_data["tasks_enqueued"]))
    return success(retry_data, trace_id=get_trace_id())


@router.post("/{import_id}/retry-parse")
def retry_document_parse(
    kb_id: UUID,
    import_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        task = enqueue_document_parse(
            db,
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
            force_reparse=True,
        )
        db.commit()
    except DocumentParseServiceError as exc:
        db.rollback()
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    background_tasks.add_task(run_document_parse_in_new_session)
    return success({"parse_task_id": str(task.parse_task_id)}, trace_id=get_trace_id())


@router.get("/{import_id}/purge-impact")
def get_file_import_purge_impact(
    kb_id: UUID,
    import_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        report = check_purge_impact(db, kb_id=kb_id, import_id=import_id)
    except FileImportPurgeServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    return success(report.to_dict(), trace_id=get_trace_id())


@router.delete("/{import_id}")
def delete_file_import(
    kb_id: UUID,
    import_id: UUID,
    deprecate_published: bool = False,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        summary = purge_file_import(
            db,
            kb_id=kb_id,
            import_id=import_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
            deprecate_published=deprecate_published,
        )
        db.commit()
    except FileImportPurgeServiceError as exc:
        db.rollback()
        return JSONResponse(
            status_code=exc.status_code,
            content=error(
                exc.code,
                str(exc),
                trace_id=get_trace_id(),
                details=exc.details,
            ),
        )
    except IntegrityError:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=error(
                "PURGE_CONFLICT",
                "Unable to purge import due to remaining references",
                trace_id=get_trace_id(),
            ),
        )
    return success(
        {
            "import_id": summary.import_id,
            "file_name": summary.file_name,
            "status": summary.status,
            "deprecated_counts": summary.deprecated_counts,
            "deleted_counts": summary.deleted_counts,
        },
        trace_id=get_trace_id(),
    )
