from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.api.schemas.writing_techniques import (
    BindSourceRequest,
    CreateWritingTechniqueRequest,
    GenerateWritingTechniqueRequest,
    UpdateWritingTechniqueRequest,
    WritingTechniqueListFilters,
)
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.writing_technique import WritingTechnique
from src.services.knowledge.writing_technique_embedding_task import (
    embed_writing_technique,
    get_writing_technique_embedding_status,
)
from src.services.knowledge.writing_technique_generate_service import (
    TechniqueChunkNotFoundError,
    TechniqueGenerateFailedError,
    TechniqueGenerateTimeoutError,
    generate_and_save_technique,
)
from src.services.knowledge.writing_technique_service import (
    TechniqueChunkBoundError,
    TechniqueConflictError,
    TechniqueNotFoundError,
    TechniqueValidationError,
    bind_source_chunk,
    create_technique,
    delete_technique,
    get_technique_by_source,
    get_technique_detail,
    list_techniques,
    publish_technique,
    update_technique,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/writing-techniques",
    tags=["writing-techniques"],
)


def _embed_technique_in_background(technique_id: UUID) -> None:
    from src.db.session import SessionLocal

    db = SessionLocal()
    try:
        embed_writing_technique(db, technique_id)
    finally:
        db.close()


def _serialize_technique_item(row: WritingTechnique, db: Session | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "technique_id": str(row.technique_id),
        "kb_id": str(row.kb_id),
        "title": row.title,
        "applicable_scene": row.applicable_scene,
        "writing_summary": row.writing_summary,
        "applicable_sections": row.applicable_sections or [],
        "tags": row.tags or [],
        "usage_mode": row.usage_mode.value,
        "recommended_outline": row.recommended_outline,
        "writing_strategy": row.writing_strategy,
        "must_include": row.must_include,
        "notes": row.notes,
        "output_requirement": row.output_requirement,
        "checklist": row.checklist,
        "confidence": row.confidence,
        "source_chunk_id": row.source_chunk_id,
        "source_invalid": row.source_invalid,
        "status": row.status.value,
        "version": row.version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if db is not None:
        payload["embedding_status"] = get_writing_technique_embedding_status(db, row.technique_id)
    return payload


@router.post("/generate")
def generate_writing_technique_api(
    kb_id: UUID,
    body: GenerateWritingTechniqueRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = generate_and_save_technique(
            db,
            kb_id=kb_id,
            chunk_id=body.chunk_id,
            confirm_overwrite=body.confirm_overwrite,
        )
        db.commit()
    except TechniqueChunkNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error("chunk_not_found", "Chunk not found", trace_id=get_trace_id()),
        )
    except TechniqueConflictError:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=error(
                "technique_exists",
                "Technique with same source already exists",
                trace_id=get_trace_id(),
            ),
        )
    except TechniqueGenerateTimeoutError:
        db.rollback()
        return JSONResponse(
            status_code=504,
            content=error(
                "technique_generate_timeout",
                "Writing technique generation timed out",
                trace_id=get_trace_id(),
            ),
        )
    except TechniqueGenerateFailedError as exc:
        db.rollback()
        logger.warning(
            "writing technique generate failed kb_id=%s chunk_id=%s reason=%s",
            kb_id,
            body.chunk_id,
            exc,
        )
        return JSONResponse(
            status_code=502,
            content=error(
                "technique_generate_failed",
                str(exc) or "Writing technique generation failed",
                trace_id=get_trace_id(),
            ),
        )
    except TechniqueValidationError as exc:
        db.rollback()
        return JSONResponse(
            status_code=422,
            content=error("validation_error", str(exc), trace_id=get_trace_id()),
        )
    return success(_serialize_technique_item(row, db), trace_id=get_trace_id())


@router.post("", status_code=201)
def create_writing_technique_api(
    kb_id: UUID,
    body: CreateWritingTechniqueRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = create_technique(db, kb_id=kb_id, payload=body.model_dump())
        db.commit()
    except TechniqueConflictError:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=error(
                "technique_exists",
                "Technique with same source already exists",
                trace_id=get_trace_id(),
            ),
        )
    except TechniqueValidationError as exc:
        db.rollback()
        return JSONResponse(
            status_code=422,
            content=error("validation_error", str(exc), trace_id=get_trace_id()),
        )
    return success(_serialize_technique_item(row, db), trace_id=get_trace_id())


@router.put("/{technique_id}")
def update_writing_technique_api(
    kb_id: UUID,
    technique_id: UUID,
    body: UpdateWritingTechniqueRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = update_technique(db, kb_id=kb_id, technique_id=technique_id, payload=body.model_dump())
        db.commit()
    except TechniqueNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error("technique_not_found", "Writing technique not found", trace_id=get_trace_id()),
        )
    except TechniqueConflictError:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=error(
                "technique_exists",
                "Technique with same source already exists",
                trace_id=get_trace_id(),
            ),
        )
    except TechniqueValidationError as exc:
        db.rollback()
        return JSONResponse(
            status_code=422,
            content=error("validation_error", str(exc), trace_id=get_trace_id()),
        )
    return success(_serialize_technique_item(row, db), trace_id=get_trace_id())


@router.put("/{technique_id}/publish")
def publish_writing_technique_api(
    kb_id: UUID,
    technique_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = publish_technique(db, kb_id=kb_id, technique_id=technique_id)
        db.commit()
    except TechniqueNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error("technique_not_found", "Writing technique not found", trace_id=get_trace_id()),
        )
    background_tasks.add_task(_embed_technique_in_background, row.technique_id)
    return success(_serialize_technique_item(row, db), trace_id=get_trace_id())


@router.put("/{technique_id}/bind-source")
def bind_source_api(
    kb_id: UUID,
    technique_id: UUID,
    body: BindSourceRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = bind_source_chunk(db, kb_id=kb_id, technique_id=technique_id, chunk_id=body.chunk_id)
        db.commit()
    except TechniqueNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error("technique_not_found", "Writing technique not found", trace_id=get_trace_id()),
        )
    except TechniqueChunkBoundError:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=error(
                "chunk_already_bound",
                "Chunk already bound by another writing technique",
                trace_id=get_trace_id(),
            ),
        )
    except TechniqueValidationError as exc:
        db.rollback()
        if str(exc) == "chunk not found":
            return JSONResponse(
                status_code=404,
                content=error("chunk_not_found", "Chunk not found", trace_id=get_trace_id()),
            )
        return JSONResponse(
            status_code=422,
            content=error("validation_error", str(exc), trace_id=get_trace_id()),
        )
    return success(_serialize_technique_item(row, db), trace_id=get_trace_id())


@router.get("")
def list_writing_techniques_api(
    kb_id: UUID,
    keyword: str | None = None,
    tags: list[str] | None = Query(default=None),
    applicable_sections: list[str] | None = Query(default=None),
    usage_mode: str | None = None,
    status: str | None = None,
    confidence_min: int | None = None,
    confidence_max: int | None = None,
    source_invalid: bool | None = None,
    has_source: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    filters = WritingTechniqueListFilters(
        keyword=keyword,
        tags=tags,
        applicable_sections=applicable_sections,
        usage_mode=usage_mode,
        status=status,
        confidence_min=confidence_min,
        confidence_max=confidence_max,
        source_invalid=source_invalid,
        has_source=has_source,
        page=page,
        page_size=page_size,
    )
    try:
        rows, total = list_techniques(db, kb_id=kb_id, filters=filters.to_service_kwargs())
    except TechniqueValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", str(exc), trace_id=get_trace_id()),
        )
    return success(
        {
            "items": [_serialize_technique_item(item, db) for item in rows],
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        },
        trace_id=get_trace_id(),
    )


@router.get("/by-source")
def get_writing_technique_by_source_api(
    kb_id: UUID,
    chunk_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = get_technique_by_source(db, kb_id=kb_id, chunk_id=chunk_id)
    if row is None:
        return success(None, trace_id=get_trace_id())
    return success(_serialize_technique_item(row, db), trace_id=get_trace_id())


@router.get("/{technique_id}")
def get_writing_technique_detail_api(
    kb_id: UUID,
    technique_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = get_technique_detail(db, kb_id=kb_id, technique_id=technique_id)
    except TechniqueNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error("technique_not_found", "Writing technique not found", trace_id=get_trace_id()),
        )
    return success(_serialize_technique_item(row, db), trace_id=get_trace_id())


@router.delete("/{technique_id}")
def delete_writing_technique_api(
    kb_id: UUID,
    technique_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        delete_technique(db, kb_id=kb_id, technique_id=technique_id)
        db.commit()
    except TechniqueNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error("technique_not_found", "Writing technique not found", trace_id=get_trace_id()),
        )
    return success({"technique_id": str(technique_id), "deleted": True}, trace_id=get_trace_id())
