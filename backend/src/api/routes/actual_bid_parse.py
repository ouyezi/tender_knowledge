from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.downstream_task_entry import DownstreamTaskEntry, DownstreamTaskType
from src.models.knowledge_base import KnowledgeBase
from src.services.actual_bid_parse_runner import (
    ActualBidParseServiceError,
    enqueue_actual_bid_parse,
    run_actual_bid_parse_in_new_session,
)
from src.api.deps import get_operator_id

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/actual-bid-parse",
    tags=["actual-bid-parse"],
)


class TriggerActualBidParseRequest(BaseModel):
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
    q = db.query(ActualBidParseTask).filter(ActualBidParseTask.kb_id == kb_id)
    if import_id:
        q = q.filter(ActualBidParseTask.import_id == import_id)
    if status:
        q = q.filter(ActualBidParseTask.status == status)
    total = q.count()
    rows = (
        q.order_by(ActualBidParseTask.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [
                {
                    "parse_task_id": str(row.parse_task_id),
                    "import_id": str(row.import_id),
                    "document_id": str(row.document_id) if row.document_id else None,
                    "bid_outline_id": str(row.bid_outline_id) if row.bid_outline_id else None,
                    "task_phase": row.task_phase.value if row.task_phase else None,
                    "status": row.status.value,
                    "parse_strategy": row.parse_strategy.value if row.parse_strategy else None,
                    "error_message": row.error_message,
                    "retry_count": row.retry_count,
                    "llm_progress": row.llm_progress,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
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


@router.post("/trigger", status_code=202)
def trigger_parse(
    kb_id: UUID,
    body: TriggerActualBidParseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        task = enqueue_actual_bid_parse(
            db,
            kb_id=kb_id,
            import_id=body.import_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
            force_reparse=body.force_reparse,
        )
    except ActualBidParseServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    background_tasks.add_task(run_actual_bid_parse_in_new_session)
    return success(
        {
            "parse_task_id": str(task.parse_task_id),
            "import_id": str(task.import_id),
            "document_id": str(task.document_id) if task.document_id else None,
            "status": task.status.value,
            "trace_id": str(task.trace_id) if task.trace_id else None,
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
        db.query(ActualBidParseTask)
        .filter(
            ActualBidParseTask.kb_id == kb_id,
            ActualBidParseTask.parse_task_id == parse_task_id,
        )
        .one_or_none()
    )
    if task is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Parse task not found", trace_id=get_trace_id()),
        )

    suggestion = (
        db.query(DocumentParseSuggestion)
        .filter(DocumentParseSuggestion.parse_task_id == parse_task_id)
        .one_or_none()
    )
    downstream_entries = (
        db.query(DownstreamTaskEntry)
        .filter(
            DownstreamTaskEntry.kb_id == kb_id,
            DownstreamTaskEntry.import_id == task.import_id,
            DownstreamTaskEntry.task_type.in_(
                [
                    DownstreamTaskType.document_parse,
                    DownstreamTaskType.bid_outline_extract,
                    DownstreamTaskType.candidate_knowledge_generate,
                ]
            ),
        )
        .order_by(DownstreamTaskEntry.created_at.asc())
        .all()
    )

    suggestion_payload = suggestion.payload if suggestion else {}
    walk_result = suggestion_payload.get("walk_result") if isinstance(suggestion_payload, dict) else {}
    if not isinstance(walk_result, dict):
        walk_result = {}

    return success(
        {
            "parse_task_id": str(task.parse_task_id),
            "import_id": str(task.import_id),
            "document_id": str(task.document_id) if task.document_id else None,
            "bid_outline_id": str(task.bid_outline_id) if task.bid_outline_id else None,
            "task_phase": task.task_phase.value if task.task_phase else None,
            "status": task.status.value,
            "parse_strategy": task.parse_strategy.value if task.parse_strategy else None,
            "error_message": task.error_message,
            "retry_count": task.retry_count,
            "llm_progress": task.llm_progress,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "created_at": task.created_at.isoformat(),
            "suggestion": (
                {
                    "outline_extract_strategy": suggestion_payload.get("outline_extract_strategy"),
                    "node_count": walk_result.get("node_count"),
                    "candidate_count": suggestion_payload.get("candidate_count"),
                    "needs_manual_review": walk_result.get("needs_manual_review"),
                }
                if suggestion
                else None
            ),
            "downstream_entries": [
                {
                    "task_type": entry.task_type.value,
                    "status": entry.status.value,
                }
                for entry in downstream_entries
            ],
        },
        trace_id=get_trace_id(),
    )
