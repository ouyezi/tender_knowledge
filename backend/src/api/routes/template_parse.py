from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.template_parse_suggestion import TemplateParseSuggestion
from src.models.template_structure_diff import (
    TemplateStructureDiff,
    TemplateStructureDiffStatus,
)
from src.models.template import Template
from src.models.template_chapter import TemplateChapter
from src.models.template_audit_log import TemplateAuditAction, TemplateAuditLog
from src.models.knowledge_base import KnowledgeBase
from src.models.template_parse_task import TemplateParseTask
from src.services.template_parse_runner import (
    TemplateParseServiceError,
    enqueue_template_parse,
    run_template_parse_in_new_session,
)
from src.services.template_confirm_service import (
    TemplateConfirmServiceError,
    confirm_parse_task,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/template-parse",
    tags=["template-parse"],
)


class TriggerParseRequest(BaseModel):
    import_id: UUID
    force_reparse: bool = False


class CreateLibraryRequest(BaseModel):
    library_name: str
    library_type: str


class ConfirmChapterRequest(BaseModel):
    temp_id: str
    parent_temp_id: str | None = None
    title: str
    level: int
    sort_order: int = 0
    chapter_taxonomy_id: UUID | None = None
    product_category_ids: list[UUID] = Field(default_factory=list)
    required: bool = False
    is_fixed_section: bool = False
    ignored: bool = False


class ConfirmMaterialRequest(BaseModel):
    temp_id: str
    chapter_temp_id: str | None = None
    material_type: str
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    product_category_ids: list[UUID] = Field(default_factory=list)
    extract_as_candidate: bool = False
    ignored: bool = False


class ConfirmCandidateActionRequest(BaseModel):
    temp_id: str
    candidate_type: str
    accepted: bool
    product_category_ids: list[UUID] = Field(default_factory=list)
    chapter_taxonomy_id: UUID | None = None
    knowledge_type: str | None = None


class ConfirmParseRequest(BaseModel):
    template_library_id: UUID | None = None
    create_library: CreateLibraryRequest | None = None
    template_name: str
    template_type: str
    product_category_ids: list[UUID] = Field(default_factory=list)
    chapters: list[ConfirmChapterRequest]
    materials: list[ConfirmMaterialRequest] = Field(default_factory=list)
    candidate_actions: list[ConfirmCandidateActionRequest] = Field(default_factory=list)


class DiffReviewRequest(BaseModel):
    diff_id: UUID | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_structure_diff(diff: TemplateStructureDiff | None) -> dict | None:
    if diff is None:
        return None
    return {
        "diff_id": str(diff.diff_id),
        "parse_task_id": str(diff.parse_task_id),
        "template_id": str(diff.template_id),
        "status": diff.status.value,
        "diff_payload": diff.diff_payload,
        "reviewed_by": diff.reviewed_by,
        "reviewed_at": diff.reviewed_at.isoformat() if diff.reviewed_at else None,
        "created_at": diff.created_at.isoformat(),
    }


def _apply_structure_tree(db: Session, *, template: Template, suggested_tree: list[dict]) -> None:
    db.query(TemplateChapter).filter(TemplateChapter.template_id == template.template_id).delete(
        synchronize_session=False
    )
    created_by_temp: dict[str, TemplateChapter] = {}
    parent_by_temp: dict[str, str | None] = {}
    for item in suggested_tree:
        temp_id = str(item.get("temp_id", "")).strip()
        if not temp_id:
            continue
        row = TemplateChapter(
            kb_id=template.kb_id,
            template_id=template.template_id,
            title=str(item.get("title", "")).strip() or temp_id,
            level=int(item.get("level", 1) or 1),
            sort_order=int(item.get("sort_order", 0) or 0),
            chapter_taxonomy_id=UUID(str(item.get("chapter_taxonomy_id")))
            if item.get("chapter_taxonomy_id")
            else None,
            product_category_ids=item.get("product_category_ids") or [],
            required=bool(item.get("required", False)),
            is_fixed_section=bool(item.get("is_fixed_section", False)),
            ignored=bool(item.get("ignored", False)),
            parse_source_ref=temp_id,
        )
        db.add(row)
        db.flush()
        created_by_temp[temp_id] = row
        parent_by_temp[temp_id] = str(item.get("parent_temp_id")) if item.get("parent_temp_id") else None

    for temp_id, row in created_by_temp.items():
        parent_temp = parent_by_temp.get(temp_id)
        if not parent_temp:
            continue
        parent = created_by_temp.get(parent_temp)
        if parent:
            row.parent_id = parent.template_chapter_id


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
            "llm_progress": row.llm_progress,
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
    structure_diff = (
        db.query(TemplateStructureDiff)
        .filter(
            TemplateStructureDiff.parse_task_id == parse_task_id,
            TemplateStructureDiff.status == TemplateStructureDiffStatus.pending_review,
        )
        .order_by(TemplateStructureDiff.created_at.desc())
        .first()
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
            "llm_progress": task.llm_progress,
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
            "structure_diff": _serialize_structure_diff(structure_diff),
        },
        trace_id=get_trace_id(),
    )


@router.get("/tasks/{parse_task_id}/suggestion")
def get_parse_suggestion(
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
    if suggestion is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Suggestion not found", trace_id=get_trace_id()),
        )
    return success(
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
        },
        trace_id=get_trace_id(),
    )


@router.post("/tasks/{parse_task_id}/confirm")
def confirm_parse(
    kb_id: UUID,
    parse_task_id: UUID,
    body: ConfirmParseRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        result = confirm_parse_task(
            db,
            kb_id=kb_id,
            parse_task_id=parse_task_id,
            body=body.model_dump(mode="json"),
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
    except TemplateConfirmServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    return success(
        {
            "parse_task_id": str(result.parse_task_id),
            "template_id": str(result.template_id),
            "template_library_id": str(result.template_library_id) if result.template_library_id else None,
            "status": result.status,
            "structure_locked_at": result.structure_locked_at.isoformat(),
            "candidate_stubs_created": result.candidate_stubs_created,
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


@router.post("/tasks/{parse_task_id}/diff/apply")
def apply_parse_diff(
    kb_id: UUID,
    parse_task_id: UUID,
    body: DiffReviewRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    query = db.query(TemplateStructureDiff).filter(
        TemplateStructureDiff.kb_id == kb_id,
        TemplateStructureDiff.parse_task_id == parse_task_id,
        TemplateStructureDiff.status == TemplateStructureDiffStatus.pending_review,
    )
    if body.diff_id:
        query = query.filter(TemplateStructureDiff.diff_id == body.diff_id)
    diff = query.order_by(TemplateStructureDiff.created_at.desc()).first()
    if diff is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Pending structure diff not found", trace_id=get_trace_id()),
        )
    template = (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_id == diff.template_id)
        .one_or_none()
    )
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    suggested_tree = (diff.diff_payload or {}).get("suggested_tree")
    if not isinstance(suggested_tree, list):
        return JSONResponse(
            status_code=422,
            content=error("INVALID_STATE", "Diff payload missing suggested_tree", trace_id=get_trace_id()),
        )
    _apply_structure_tree(db, template=template, suggested_tree=suggested_tree)
    diff.status = TemplateStructureDiffStatus.applied
    diff.reviewed_by = operator_id
    task_finished_at = _now()
    diff.reviewed_at = task_finished_at
    db.add(
        TemplateAuditLog(
            trace_id=get_trace_id(),
            kb_id=kb_id,
            template_id=template.template_id,
            template_library_id=template.template_library_id,
            import_id=template.source_import_id,
            operator_id=operator_id,
            action=TemplateAuditAction.diff_apply,
            payload_summary={"diff_id": str(diff.diff_id), "parse_task_id": str(parse_task_id)},
        )
    )
    db.commit()
    return success(
        {
            "parse_task_id": str(parse_task_id),
            "template_id": str(template.template_id),
            "structure_diff": _serialize_structure_diff(diff),
            "applied_at": task_finished_at.isoformat() if task_finished_at else None,
        },
        trace_id=get_trace_id(),
    )


@router.post("/tasks/{parse_task_id}/diff/reject")
def reject_parse_diff(
    kb_id: UUID,
    parse_task_id: UUID,
    body: DiffReviewRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    query = db.query(TemplateStructureDiff).filter(
        TemplateStructureDiff.kb_id == kb_id,
        TemplateStructureDiff.parse_task_id == parse_task_id,
        TemplateStructureDiff.status == TemplateStructureDiffStatus.pending_review,
    )
    if body.diff_id:
        query = query.filter(TemplateStructureDiff.diff_id == body.diff_id)
    diff = query.order_by(TemplateStructureDiff.created_at.desc()).first()
    if diff is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Pending structure diff not found", trace_id=get_trace_id()),
        )
    diff.status = TemplateStructureDiffStatus.rejected
    diff.reviewed_by = operator_id
    template_updated_at = _now()
    diff.reviewed_at = template_updated_at
    template = (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_id == diff.template_id)
        .one_or_none()
    )
    db.add(
        TemplateAuditLog(
            trace_id=get_trace_id(),
            kb_id=kb_id,
            template_id=template.template_id if template else None,
            template_library_id=template.template_library_id if template else None,
            import_id=template.source_import_id if template else None,
            operator_id=operator_id,
            action=TemplateAuditAction.diff_reject,
            payload_summary={"diff_id": str(diff.diff_id), "parse_task_id": str(parse_task_id)},
        )
    )
    db.commit()
    return success(
        {
            "parse_task_id": str(parse_task_id),
            "template_id": str(diff.template_id),
            "structure_diff": _serialize_structure_diff(diff),
            "rejected_at": template_updated_at.isoformat() if template_updated_at else None,
        },
        trace_id=get_trace_id(),
    )
