from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.api.schemas.blueprints import (
    BlueprintListFilters,
    GenerateBlueprintRequest,
    SaveBlueprintRequest,
)
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.knowledge_blueprint import KnowledgeBlueprint
from src.services.knowledge.blueprint_generate_service import (
    BlueprintGenerateFailedError,
    BlueprintGenerateTimeoutError,
    NoChildNodesError,
    generate_blueprint_draft,
)
from src.services.knowledge.blueprint_service import (
    BlueprintConflictError,
    BlueprintNotFoundError,
    BlueprintValidationError,
    create_blueprint,
    delete_blueprint,
    get_blueprint_by_source,
    get_blueprint_detail,
    list_blueprints,
    update_blueprint,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/blueprints",
    tags=["blueprints"],
)


def _serialize_blueprint_item(row: KnowledgeBlueprint) -> dict[str, object]:
    return {
        "blueprint_id": str(row.blueprint_id),
        "kb_id": str(row.kb_id),
        "name": row.name,
        "description": row.description,
        "source_doc_id": str(row.source_doc_id),
        "source_node_id": str(row.source_node_id),
        "source_chapter_title": row.source_chapter_title,
        "product_tags": row.product_tags or [],
        "industry_tags": row.industry_tags or [],
        "scenario_tags": row.scenario_tags or [],
        "status": row.status.value,
        "version": row.version,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post("/generate")
def generate_blueprint_draft_api(
    kb_id: UUID,
    body: GenerateBlueprintRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        draft = generate_blueprint_draft(
            db,
            kb_id=kb_id,
            doc_id=body.doc_id,
            node_id=body.node_id,
        )
    except NoChildNodesError:
        return JSONResponse(
            status_code=400,
            content=error("no_child_nodes", "No child nodes under source node", trace_id=get_trace_id()),
        )
    except BlueprintGenerateTimeoutError:
        return JSONResponse(
            status_code=504,
            content=error(
                "blueprint_generate_timeout",
                "Blueprint generation timed out",
                trace_id=get_trace_id(),
            ),
        )
    except BlueprintGenerateFailedError:
        return JSONResponse(
            status_code=502,
            content=error(
                "blueprint_generate_failed",
                "Blueprint generation failed",
                trace_id=get_trace_id(),
            ),
        )
    return success(draft, trace_id=get_trace_id())


@router.get("/by-source")
def get_blueprint_by_source_api(
    kb_id: UUID,
    doc_id: UUID = Query(...),
    node_id: UUID = Query(...),
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = get_blueprint_by_source(db, kb_id=kb_id, source_node_id=node_id)
    if row is None or row.source_doc_id != doc_id:
        return success(None, trace_id=get_trace_id())
    return success(_serialize_blueprint_item(row), trace_id=get_trace_id())


@router.post("", status_code=201)
def create_blueprint_api(
    kb_id: UUID,
    body: SaveBlueprintRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = create_blueprint(db, kb_id=kb_id, payload=body.model_dump())
        db.commit()
    except BlueprintConflictError:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=error(
                "blueprint_source_exists",
                "Blueprint with same source already exists",
                trace_id=get_trace_id(),
            ),
        )
    except BlueprintValidationError as exc:
        db.rollback()
        return JSONResponse(
            status_code=422,
            content=error("validation_error", str(exc), trace_id=get_trace_id()),
        )
    return success(_serialize_blueprint_item(row), trace_id=get_trace_id())


@router.put("/{blueprint_id}")
def update_blueprint_api(
    kb_id: UUID,
    blueprint_id: UUID,
    body: SaveBlueprintRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        row = update_blueprint(db, kb_id=kb_id, blueprint_id=blueprint_id, payload=body.model_dump())
        db.commit()
    except BlueprintNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error("blueprint_not_found", "Blueprint not found", trace_id=get_trace_id()),
        )
    except BlueprintValidationError as exc:
        db.rollback()
        return JSONResponse(
            status_code=422,
            content=error("validation_error", str(exc), trace_id=get_trace_id()),
        )
    return success(_serialize_blueprint_item(row), trace_id=get_trace_id())


@router.get("")
def list_blueprints_api(
    kb_id: UUID,
    keyword: str | None = None,
    product_tags: list[str] | None = Query(default=None),
    industry_tags: list[str] | None = Query(default=None),
    scenario_tags: list[str] | None = Query(default=None),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    filters = BlueprintListFilters(
        keyword=keyword,
        product_tags=product_tags,
        industry_tags=industry_tags,
        scenario_tags=scenario_tags,
        page=page,
        page_size=page_size,
    )
    rows, total = list_blueprints(db, kb_id=kb_id, **filters.to_service_kwargs())
    return success(
        {
            "items": [_serialize_blueprint_item(item) for item in rows],
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        },
        trace_id=get_trace_id(),
    )


@router.get("/{blueprint_id}")
def get_blueprint_detail_api(
    kb_id: UUID,
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        payload = get_blueprint_detail(db, kb_id=kb_id, blueprint_id=blueprint_id)
    except BlueprintNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error("blueprint_not_found", "Blueprint not found", trace_id=get_trace_id()),
        )
    return success(payload, trace_id=get_trace_id())


@router.delete("/{blueprint_id}")
def delete_blueprint_api(
    kb_id: UUID,
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        delete_blueprint(db, kb_id=kb_id, blueprint_id=blueprint_id)
        db.commit()
    except BlueprintNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error("blueprint_not_found", "Blueprint not found", trace_id=get_trace_id()),
        )
    return success({"blueprint_id": str(blueprint_id), "deleted": True}, trace_id=get_trace_id())
