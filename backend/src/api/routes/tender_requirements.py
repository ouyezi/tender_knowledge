from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_operator_id, get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.tender_requirement_context import TenderRequirementStatus
from src.services.generation.tender_requirement_service import (
    TenderRequirementService,
    TenderRequirementValidationError,
    serialize_tender_requirement,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/tender-requirements",
    tags=["tender-requirements"],
)


class TenderRequirementCreateRequest(BaseModel):
    title: str
    outline_structure: dict = Field(default_factory=dict)
    outline_nodes: list[dict] = Field(default_factory=list)
    score_points: list[dict] = Field(default_factory=list)
    rejection_clauses: list[str] = Field(default_factory=list)
    format_requirements: list[str] = Field(default_factory=list)
    qualification_requirements: list[str] = Field(default_factory=list)
    response_clauses: list[str] = Field(default_factory=list)
    source_note: str | None = None


class TenderRequirementUpdateRequest(BaseModel):
    title: str | None = None
    outline_structure: dict | None = None
    outline_nodes: list[dict] | None = None
    score_points: list[dict] | None = None
    rejection_clauses: list[str] | None = None
    format_requirements: list[str] | None = None
    qualification_requirements: list[str] | None = None
    response_clauses: list[str] | None = None
    source_note: str | None = None
    status: str | None = None


@router.post("")
def create_tender_requirement(
    kb_id: UUID,
    body: TenderRequirementCreateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = TenderRequirementService(db)
    try:
        row = service.create(
            kb_id=kb_id,
            title=body.title,
            outline_structure=body.outline_structure,
            outline_nodes=body.outline_nodes,
            score_points=body.score_points,
            rejection_clauses=body.rejection_clauses,
            format_requirements=body.format_requirements,
            qualification_requirements=body.qualification_requirements,
            response_clauses=body.response_clauses,
            source_note=body.source_note,
            operator_id=get_operator_id(),
        )
    except TenderRequirementValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    db.commit()
    return success(serialize_tender_requirement(row), trace_id=get_trace_id())


@router.get("/{requirement_context_id}")
def get_tender_requirement(
    kb_id: UUID,
    requirement_context_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = TenderRequirementService(db).get(
        kb_id=kb_id,
        requirement_context_id=requirement_context_id,
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "tender requirement context not found", trace_id=get_trace_id()),
        )
    return success(serialize_tender_requirement(row, full=True), trace_id=get_trace_id())


@router.get("")
def list_tender_requirements(
    kb_id: UUID,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    status_filter = TenderRequirementStatus(status) if status else None
    rows, total = TenderRequirementService(db).list(
        kb_id=kb_id,
        status=status_filter,
        q=q,
        page=max(1, page),
        page_size=max(1, min(200, page_size)),
    )
    return success(
        {
            "items": [serialize_tender_requirement(row, full=True) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


@router.patch("/{requirement_context_id}")
def update_tender_requirement(
    kb_id: UUID,
    requirement_context_id: UUID,
    body: TenderRequirementUpdateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = TenderRequirementService(db)
    row = service.get(kb_id=kb_id, requirement_context_id=requirement_context_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "tender requirement context not found", trace_id=get_trace_id()),
        )
    status_filter = TenderRequirementStatus(body.status) if body.status else None
    try:
        row = service.update(
            row,
            title=body.title,
            outline_structure=body.outline_structure,
            outline_nodes=body.outline_nodes,
            score_points=body.score_points,
            rejection_clauses=body.rejection_clauses,
            format_requirements=body.format_requirements,
            qualification_requirements=body.qualification_requirements,
            response_clauses=body.response_clauses,
            source_note=body.source_note,
            status=status_filter,
        )
    except TenderRequirementValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    db.commit()
    return success(serialize_tender_requirement(row, full=True), trace_id=get_trace_id())


@router.post("/{requirement_context_id}/archive")
def archive_tender_requirement(
    kb_id: UUID,
    requirement_context_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = TenderRequirementService(db)
    row = service.get(kb_id=kb_id, requirement_context_id=requirement_context_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "tender requirement context not found", trace_id=get_trace_id()),
        )
    row = service.archive(row)
    db.commit()
    return success(serialize_tender_requirement(row, full=True), trace_id=get_trace_id())
