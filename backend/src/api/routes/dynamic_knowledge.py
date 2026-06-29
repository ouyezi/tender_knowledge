from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.api.schemas.dynamic_knowledge import (
    CreateDynamicKnowledgeRequest,
    DynamicKnowledgeListFilters,
    UpdateDynamicKnowledgeRequest,
)
from src.db.session import get_db
from src.models.dynamic_knowledge_record import DynamicKnowledgeRecord
from src.models.knowledge_base import KnowledgeBase
from src.services.knowledge.dynamic_knowledge_service import (
    DynamicKnowledgeNotFoundError,
    create_record,
    delete_record,
    get_record,
    list_records,
    update_record,
)
from src.services.knowledge.taxonomy_field_utils import compute_is_expired
from src.services.knowledge.taxonomy_service import (
    TaxonomyValidationError,
    expand_business_line_labels,
    get_taxonomy_label,
)

router = APIRouter(prefix="/api/v1/kbs/{kb_id}/dynamic-knowledge", tags=["dynamic-knowledge"])


def _serialize(row: DynamicKnowledgeRecord, db: Session) -> dict:
    return {
        "id": row.id,
        "kb_id": str(row.kb_id),
        "dynamic_type_code": row.dynamic_type_code,
        "dynamic_type_label": get_taxonomy_label(db, "dynamic_type", row.dynamic_type_code),
        "title": row.title,
        "content": row.content,
        "structured_data": row.structured_data,
        "business_line_codes": row.business_line_codes or [],
        "business_line_labels": expand_business_line_labels(db, row.business_line_codes or []),
        "source_type": row.source_type,
        "source_doc_id": str(row.source_doc_id) if row.source_doc_id else None,
        "source_chunk_id": row.source_chunk_id,
        "issue_date": row.issue_date.isoformat() if row.issue_date else None,
        "expire_date": row.expire_date.isoformat() if row.expire_date else None,
        "is_expired": compute_is_expired(row.expire_date),
        "status": row.status,
        "sync_status": row.sync_status,
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        "content_hash": row.content_hash,
        "create_time": row.create_time.isoformat() if row.create_time else None,
        "update_time": row.update_time.isoformat() if row.update_time else None,
    }


@router.post("", status_code=201)
def create_dynamic_knowledge_api(
    kb_id: UUID,
    body: CreateDynamicKnowledgeRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = create_record(db, kb_id=kb_id, payload=body.model_dump())
        db.commit()
    except TaxonomyValidationError as exc:
        db.rollback()
        return JSONResponse(
            status_code=422,
            content=error("validation_error", str(exc), trace_id=get_trace_id()),
        )
    return success(_serialize(row, db), trace_id=get_trace_id())


@router.get("")
def list_dynamic_knowledge_api(
    kb_id: UUID,
    dynamic_type_code: str | None = None,
    status: str | None = None,
    business_line_codes: list[str] | None = Query(default=None),
    expired_only: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    filters = DynamicKnowledgeListFilters(
        dynamic_type_code=dynamic_type_code,
        status=status,
        business_line_codes=business_line_codes,
        expired_only=expired_only,
        page=page,
        page_size=page_size,
    )
    rows, total = list_records(db, kb_id=kb_id, filters=filters.model_dump())
    return success(
        {
            "items": [_serialize(row, db) for row in rows],
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        },
        trace_id=get_trace_id(),
    )


@router.get("/{record_id}")
def get_dynamic_knowledge_api(
    kb_id: UUID,
    record_id: int,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = get_record(db, kb_id=kb_id, record_id=record_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error(
                "DYNAMIC_KNOWLEDGE_NOT_FOUND",
                "Dynamic knowledge not found",
                trace_id=get_trace_id(),
            ),
        )
    return success(_serialize(row, db), trace_id=get_trace_id())


@router.put("/{record_id}")
def update_dynamic_knowledge_api(
    kb_id: UUID,
    record_id: int,
    body: UpdateDynamicKnowledgeRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = update_record(
            db,
            kb_id=kb_id,
            record_id=record_id,
            payload=body.model_dump(exclude_unset=True),
        )
        db.commit()
    except DynamicKnowledgeNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error(
                "DYNAMIC_KNOWLEDGE_NOT_FOUND",
                "Dynamic knowledge not found",
                trace_id=get_trace_id(),
            ),
        )
    except TaxonomyValidationError as exc:
        db.rollback()
        return JSONResponse(
            status_code=422,
            content=error("validation_error", str(exc), trace_id=get_trace_id()),
        )
    return success(_serialize(row, db), trace_id=get_trace_id())


@router.delete("/{record_id}")
def delete_dynamic_knowledge_api(
    kb_id: UUID,
    record_id: int,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        delete_record(db, kb_id=kb_id, record_id=record_id)
        db.commit()
    except DynamicKnowledgeNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error(
                "DYNAMIC_KNOWLEDGE_NOT_FOUND",
                "Dynamic knowledge not found",
                trace_id=get_trace_id(),
            ),
        )
    return success({"id": record_id, "deleted": True}, trace_id=get_trace_id())
