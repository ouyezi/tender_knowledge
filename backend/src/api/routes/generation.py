from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.chapter_draft import ChapterDraft, DraftOutcomeStatus
from src.models.generation_task import GenerationTask
from src.models.knowledge_base import KnowledgeBase
from src.schemas.generation import GenerationDraftCreateRequest, GenerationDraftRegenerateRequest
from src.services.generation.generation_runner import run_generation_task_in_new_session
from src.services.generation.generation_service import (
    GenerationService,
    GenerationServiceError,
    serialize_chapter_draft,
    serialize_generation_snapshot,
)
from src.services.llm_client import is_llm_available
from src.services.generation.variable_resolver import (
    GenerationPreflightError,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/generation",
    tags=["generation"],
)


@router.post("/drafts")
def create_generation_draft(
    kb_id: UUID,
    body: GenerationDraftCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: KnowledgeBase = Depends(get_kb_or_404),
    operator_id: str = Depends(get_operator_id),
):
    if not is_llm_available():
        return JSONResponse(
            status_code=503,
            content=error(
                "LLM_UNAVAILABLE",
                "LLM service is unavailable",
                trace_id=get_trace_id(),
            ),
        )

    service = GenerationService(db)
    try:
        task = service.create_draft_task(
            kb_id=kb_id,
            body=body,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
    except GenerationPreflightError as exc:
        status_code = 404 if exc.code == "NOT_FOUND" else 422
        return JSONResponse(
            status_code=status_code,
            content=error(
                exc.code,
                str(exc),
                details=exc.details,
                trace_id=get_trace_id(),
            ),
        )
    db.commit()
    background_tasks.add_task(run_generation_task_in_new_session, task.task_id)
    return JSONResponse(
        status_code=202,
        content=success(
            {
                "task_id": str(task.task_id),
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
            },
            trace_id=get_trace_id(),
        ),
    )


@router.get("/tasks/{task_id}")
def get_generation_task(
    kb_id: UUID,
    task_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    task = (
        db.query(GenerationTask)
        .filter(GenerationTask.kb_id == kb_id, GenerationTask.task_id == task_id)
        .one_or_none()
    )
    if task is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "generation task not found", trace_id=get_trace_id()),
        )
    snapshot_id = None
    if task.draft_id:
        draft = db.get(ChapterDraft, task.draft_id)
        if draft is not None:
            snapshot_id = str(draft.snapshot_id)
    return success(
        {
            "task_id": str(task.task_id),
            "status": task.status.value,
            "requirement_context_id": str(task.requirement_context_id),
            "suggestion_id": str(task.suggestion_id) if task.suggestion_id else None,
            "target_outline_node": task.target_outline_node,
            "draft_id": str(task.draft_id) if task.draft_id else None,
            "snapshot_id": snapshot_id,
            "error_code": task.error_code,
            "error_message": task.error_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        },
        trace_id=get_trace_id(),
    )


@router.get("/drafts/{draft_id}")
def get_generation_draft(
    kb_id: UUID,
    draft_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = GenerationService(db).get_draft(kb_id=kb_id, draft_id=draft_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "chapter draft not found", trace_id=get_trace_id()),
        )
    return success(serialize_chapter_draft(row, full=True), trace_id=get_trace_id())


@router.post("/drafts/{draft_id}/accept")
def accept_generation_draft(
    kb_id: UUID,
    draft_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: KnowledgeBase = Depends(get_kb_or_404),
    operator_id: str = Depends(get_operator_id),
):
    service = GenerationService(db)
    try:
        draft = service.accept_draft(kb_id=kb_id, draft_id=draft_id, operator_id=operator_id)
    except GenerationServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    db.commit()
    return success(
        {
            "draft_id": str(draft.draft_id),
            "outcome_status": draft.outcome_status.value,
            "outcome_at": draft.outcome_at.isoformat() if draft.outcome_at else None,
        },
        trace_id=get_trace_id(),
    )


@router.post("/drafts/{draft_id}/discard")
def discard_generation_draft(
    kb_id: UUID,
    draft_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: KnowledgeBase = Depends(get_kb_or_404),
    operator_id: str = Depends(get_operator_id),
):
    service = GenerationService(db)
    try:
        draft = service.discard_draft(kb_id=kb_id, draft_id=draft_id, operator_id=operator_id)
    except GenerationServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    db.commit()
    return success(
        {
            "draft_id": str(draft.draft_id),
            "outcome_status": draft.outcome_status.value,
            "is_active": draft.is_active,
        },
        trace_id=get_trace_id(),
    )


@router.post("/drafts/{draft_id}/regenerate")
def regenerate_generation_draft(
    kb_id: UUID,
    draft_id: UUID,
    body: GenerationDraftRegenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: KnowledgeBase = Depends(get_kb_or_404),
    operator_id: str = Depends(get_operator_id),
):
    if not is_llm_available():
        return JSONResponse(
            status_code=503,
            content=error(
                "LLM_UNAVAILABLE",
                "LLM service is unavailable",
                trace_id=get_trace_id(),
            ),
        )

    service = GenerationService(db)
    try:
        task = service.regenerate_draft(
            kb_id=kb_id,
            draft_id=draft_id,
            body=body,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
    except GenerationPreflightError as exc:
        status_code = 404 if exc.code == "NOT_FOUND" else 422
        return JSONResponse(
            status_code=status_code,
            content=error(
                exc.code,
                str(exc),
                details=exc.details,
                trace_id=get_trace_id(),
            ),
        )
    except GenerationServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    db.commit()
    background_tasks.add_task(run_generation_task_in_new_session, task.task_id)
    return JSONResponse(
        status_code=202,
        content=success(
            {
                "task_id": str(task.task_id),
                "status": task.status.value,
                "created_at": task.created_at.isoformat(),
            },
            trace_id=get_trace_id(),
        ),
    )


@router.get("/drafts")
def list_generation_drafts(
    kb_id: UUID,
    target_title: str | None = None,
    requirement_context_id: UUID | None = None,
    outcome_status: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    status_filter = DraftOutcomeStatus(outcome_status) if outcome_status else None
    rows, total = GenerationService(db).list_drafts(
        kb_id=kb_id,
        target_title=target_title,
        requirement_context_id=requirement_context_id,
        outcome_status=status_filter,
        is_active=is_active,
        page=max(1, page),
        page_size=max(1, min(200, page_size)),
    )
    return success(
        {
            "items": [serialize_chapter_draft(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


@router.get("/snapshots/{snapshot_id}")
def get_generation_snapshot(
    kb_id: UUID,
    snapshot_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = GenerationService(db).get_snapshot(kb_id=kb_id, snapshot_id=snapshot_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "generation snapshot not found", trace_id=get_trace_id()),
        )
    return success(serialize_generation_snapshot(row, full=True), trace_id=get_trace_id())


@router.get("/snapshots")
def list_generation_snapshots(
    kb_id: UUID,
    requirement_context_id: UUID | None = None,
    target_title: str | None = None,
    from_dt: str | None = Query(None, alias="from"),
    to_dt: str | None = Query(None, alias="to"),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    parsed_from = _parse_iso_datetime(from_dt) if from_dt else None
    parsed_to = _parse_iso_datetime(to_dt) if to_dt else None
    rows, total = GenerationService(db).list_snapshots(
        kb_id=kb_id,
        requirement_context_id=requirement_context_id,
        target_title=target_title,
        from_dt=parsed_from,
        to_dt=parsed_to,
        page=max(1, page),
        page_size=max(1, min(200, page_size)),
    )
    return success(
        {
            "items": [serialize_generation_snapshot(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


def _parse_iso_datetime(value: str):
    from datetime import datetime

    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)
