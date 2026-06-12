from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.template_library import TemplateLibrary
from src.services.template_publish_service import (
    TemplatePublishServiceError,
    publish_template_library,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/template-libraries",
    tags=["template-libraries"],
)


class PublishLibraryRequest(BaseModel):
    cascade_templates: bool = True
    version_note: str | None = None


@router.get("")
def list_template_libraries(
    kb_id: UUID,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(TemplateLibrary).filter(TemplateLibrary.kb_id == kb_id)
    if status:
        q = q.filter(TemplateLibrary.status == status)
    total = q.count()
    rows = (
        q.order_by(TemplateLibrary.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "template_library_id": str(row.template_library_id),
            "library_name": row.library_name,
            "library_type": row.library_type.value,
            "status": row.status.value,
            "version": row.version,
            "updated_at": row.updated_at.isoformat(),
        }
        for row in rows
    ]
    return success(
        {"items": items, "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )


@router.post("/{template_library_id}/publish")
def publish_library(
    kb_id: UUID,
    template_library_id: UUID,
    body: PublishLibraryRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
    operator_id: str = Depends(get_operator_id),
):
    try:
        result = publish_template_library(
            db,
            kb_id=kb_id,
            template_library_id=template_library_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
            cascade_templates=body.cascade_templates,
        )
    except TemplatePublishServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    return success(
        {
            "template_library_id": str(result.object_id),
            "status": result.status,
            "version": result.version,
            "version_no": result.version_no,
            "snapshot_id": str(result.snapshot_id),
            "published_at": result.published_at.isoformat(),
        },
        trace_id=get_trace_id(),
    )
