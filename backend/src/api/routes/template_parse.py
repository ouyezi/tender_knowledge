from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.template_parse_suggestion import TemplateParseSuggestion
from src.models.knowledge_base import KnowledgeBase
from src.models.template_parse_task import TemplateParseTask
from src.services.template_parse_runner import (
    TemplateParseServiceError,
    enqueue_template_parse,
    run_template_parse_in_new_session,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/template-parse",
    tags=["template-parse"],
)


class TriggerParseRequest(BaseModel):
    import_id: UUID
    force_reparse: bool = False


@router.get("/tasks")
def list_parse_tasks(
    kb_id: UUID,
    import_id: UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(TemplateParseTask).filter(TemplateParseTask.kb_id == kb_id)
    if import_id:
        q = q.filter(TemplateParseTask.import_id == import_id)
    if status:
        q = q.filter(TemplateParseTask.status == status)
    total = q.count()
    rows = (
        q.order_by(TemplateParseTask.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "parse_task_id": str(row.parse_task_id),
            "import_id": str(row.import_id),
            "template_id": str(row.template_id) if row.template_id else None,
            "status": row.status.value,
            "parse_strategy": row.parse_strategy.value if row.parse_strategy else None,
            "error_message": row.error_message,
            "retry_count": row.retry_count,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
    return success(
        {"items": items, "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )


@router.post("/trigger", status_code=202)
def trigger_parse(
    kb_id: UUID,
    body: TriggerParseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        task = enqueue_template_parse(
            db,
            kb_id=kb_id,
            import_id=body.import_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
            force_reparse=body.force_reparse,
        )
    except TemplateParseServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    background_tasks.add_task(run_template_parse_in_new_session)
    return success(
        {
            "parse_task_id": str(task.parse_task_id),
            "import_id": str(task.import_id),
            "template_id": str(task.template_id) if task.template_id else None,
            "status": task.status.value,
            "trace_id": str(task.trace_id),
        },
        trace_id=get_trace_id(),
    )


@router.get("/tasks/{parse_task_id}")
def get_parse_task(
    kb_id: UUID,
    parse_task_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    task = (
        db.query(TemplateParseTask)
        .filter(TemplateParseTask.kb_id == kb_id, TemplateParseTask.parse_task_id == parse_task_id)
        .one_or_none()
    )
    if task is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Parse task not found", trace_id=get_trace_id()),
        )
    suggestion = (
        db.query(TemplateParseSuggestion)
        .filter(TemplateParseSuggestion.parse_task_id == parse_task_id)
        .one_or_none()
    )
    return success(
        {
            "parse_task_id": str(task.parse_task_id),
            "import_id": str(task.import_id),
            "template_id": str(task.template_id) if task.template_id else None,
            "status": task.status.value,
            "parse_strategy": task.parse_strategy.value if task.parse_strategy else None,
            "log_lines": task.log_lines or [],
            "error_message": task.error_message,
            "retry_count": task.retry_count,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "suggestion": (
                {
                    "suggestion_id": str(suggestion.suggestion_id),
                    "suggested_library_id": str(suggestion.suggested_library_id)
                    if suggestion.suggested_library_id
                    else None,
                    "suggested_library_name": suggestion.suggested_library_name,
                    "suggested_product_category_ids": suggestion.suggested_product_category_ids,
                    "suggested_chapter_tree": suggestion.suggested_chapter_tree,
                    "suggested_materials": suggestion.suggested_materials,
                    "suggested_candidates": suggestion.suggested_candidates,
                    "suggestion_source": suggestion.suggestion_source.value,
                    "rationale": suggestion.rationale,
                }
                if suggestion
                else None
            ),
        },
        trace_id=get_trace_id(),
    )


@router.post("/tasks/{parse_task_id}/retry", status_code=202)
def retry_parse_task(
    kb_id: UUID,
    parse_task_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    task = (
        db.query(TemplateParseTask)
        .filter(TemplateParseTask.kb_id == kb_id, TemplateParseTask.parse_task_id == parse_task_id)
        .one_or_none()
    )
    if task is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Parse task not found", trace_id=get_trace_id()),
        )
    if task.status.value != "failed":
        return JSONResponse(
            status_code=422,
            content=error("INVALID_STATE", "Only failed tasks can be retried", trace_id=get_trace_id()),
        )
    try:
        new_task = enqueue_template_parse(
            db,
            kb_id=kb_id,
            import_id=task.import_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
            force_reparse=True,
        )
    except TemplateParseServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    background_tasks.add_task(run_template_parse_in_new_session)
    return success(
        {
            "parse_task_id": str(new_task.parse_task_id),
            "import_id": str(new_task.import_id),
            "status": new_task.status.value,
        },
        trace_id=get_trace_id(),
    )
