from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.chapter_pattern import ChapterPattern, ChapterPatternStatus
from src.models.chapter_pattern_mining_task import ChapterPatternMiningTask
from src.models.knowledge_base import KnowledgeBase
from src.services.chapter_pattern_miner import (
    ChapterPatternMiningServiceError,
    enqueue_chapter_pattern_mining,
    run_chapter_pattern_mining_in_new_session,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/chapter-patterns",
    tags=["chapter-patterns"],
)


class TriggerChapterPatternMiningRequest(BaseModel):
    min_frequency: int = Field(default=2, ge=2)
    include_template_chapters: bool = True


def _serialize_pattern(item: ChapterPattern) -> dict:
    return {
        "pattern_id": str(item.pattern_id),
        "pattern_name": item.pattern_name,
        "chapter_taxonomy_id": str(item.chapter_taxonomy_id) if item.chapter_taxonomy_id else None,
        "frequency": item.frequency,
        "status": item.status.value,
        "source_outline_ids": item.source_outline_ids or [],
        "source_template_chapter_ids": item.source_template_chapter_ids or [],
        "common_child_chapters": item.common_child_chapters or [],
    }


@router.post("/mine", status_code=202)
def trigger_chapter_pattern_mining(
    kb_id: UUID,
    body: TriggerChapterPatternMiningRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    trace_id = get_trace_id()
    try:
        task = enqueue_chapter_pattern_mining(
            db,
            kb_id=kb_id,
            operator_id=operator_id,
            min_frequency=body.min_frequency,
            include_template_chapters=body.include_template_chapters,
        )
    except ChapterPatternMiningServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=trace_id),
        )
    background_tasks.add_task(run_chapter_pattern_mining_in_new_session)
    return success(
        {
            "mining_task_id": str(task.mining_task_id),
            "status": task.status.value,
            "trace_id": str(trace_id),
        },
        trace_id=trace_id,
    )


@router.get("/mine/tasks/{mining_task_id}")
def get_chapter_pattern_mining_task(
    kb_id: UUID,
    mining_task_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    task = (
        db.query(ChapterPatternMiningTask)
        .filter(
            ChapterPatternMiningTask.kb_id == kb_id,
            ChapterPatternMiningTask.mining_task_id == mining_task_id,
        )
        .one_or_none()
    )
    if task is None:
        return JSONResponse(
            status_code=404,
            content=error("MINING_TASK_NOT_FOUND", "Mining task not found", trace_id=get_trace_id()),
        )
    return success(
        {
            "mining_task_id": str(task.mining_task_id),
            "status": task.status.value,
            "result_summary": task.result_summary,
            "error_message": task.error_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "created_at": task.created_at.isoformat(),
        },
        trace_id=get_trace_id(),
    )


@router.get("")
def list_chapter_patterns(
    kb_id: UUID,
    status: str | None = "candidate",
    chapter_taxonomy_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    resolved_status = None
    if status:
        try:
            resolved_status = ChapterPatternStatus(status)
        except ValueError:
            return JSONResponse(
                status_code=422,
                content=error("VALIDATION", "invalid status", trace_id=get_trace_id()),
            )
    offset = max(page - 1, 0) * page_size
    q = db.query(ChapterPattern).filter(ChapterPattern.kb_id == kb_id)
    if resolved_status:
        q = q.filter(ChapterPattern.status == resolved_status)
    if chapter_taxonomy_id:
        q = q.filter(ChapterPattern.chapter_taxonomy_id == chapter_taxonomy_id)
    total = q.count()
    rows = (
        q.order_by(ChapterPattern.frequency.desc(), ChapterPattern.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [_serialize_pattern(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )
