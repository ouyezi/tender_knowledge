from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.candidate_knowledge_stub import (
    CandidateKnowledgeStub,
    CandidateKnowledgeStubStatus,
)
from src.models.knowledge_base import KnowledgeBase
from src.models.template import Template
from src.services.template_publish_service import (
    TemplatePublishServiceError,
    publish_template,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/templates",
    tags=["templates"],
)


class PublishTemplateRequest(BaseModel):
    version_note: str | None = None


@router.get("")
def list_templates(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    uncategorized: bool = False,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(Template).filter(Template.kb_id == kb_id)
    if uncategorized:
        q = q.filter(Template.template_library_id.is_(None))
    total = q.count()
    rows = (
        q.order_by(Template.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "template_id": str(row.template_id),
            "template_name": row.template_name,
            "template_library_id": str(row.template_library_id)
            if row.template_library_id
            else None,
            "status": row.status.value,
            "confirmed": row.confirmed,
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]
    return success(
        {"items": items, "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )


@router.post("/{template_id}/publish")
def publish_template_endpoint(
    kb_id: UUID,
    template_id: UUID,
    _body: PublishTemplateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
    operator_id: str = Depends(get_operator_id),
):
    try:
        result = publish_template(
            db,
            kb_id=kb_id,
            template_id=template_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
    except TemplatePublishServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    return success(
        {
            "template_id": str(result.object_id),
            "status": result.status,
            "version": result.version,
            "version_no": result.version_no,
            "snapshot_id": str(result.snapshot_id),
            "published_at": result.published_at.isoformat(),
        },
        trace_id=get_trace_id(),
    )


@router.get("/{template_id}/candidate-stubs")
def list_candidate_stubs(
    kb_id: UUID,
    template_id: UUID,
    status: CandidateKnowledgeStubStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    template = (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_id == template_id)
        .one_or_none()
    )
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )

    offset = max(page - 1, 0) * page_size
    query = db.query(CandidateKnowledgeStub).filter(
        CandidateKnowledgeStub.kb_id == kb_id,
        CandidateKnowledgeStub.template_id == template_id,
    )
    if status:
        query = query.filter(CandidateKnowledgeStub.status == status)
    total = query.count()
    rows = (
        query.order_by(CandidateKnowledgeStub.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [
                {
                    "stub_id": str(row.stub_id),
                    "candidate_type": row.candidate_type.value,
                    "title": row.title,
                    "summary": row.summary,
                    "content_preview": row.content_preview,
                    "status": row.status.value,
                    "template_chapter_id": str(row.template_chapter_id) if row.template_chapter_id else None,
                    "material_id": str(row.material_id) if row.material_id else None,
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )
