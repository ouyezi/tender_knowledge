from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.api.schemas.blueprints import (
    BlueprintListFilters,
    BlueprintSearchRequest,
    GenerateBlueprintRequest,
    ParseSearchQueryRequest,
    SaveBlueprintRequest,
    SuggestOutlineRequest,
)
from src.config import settings
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.knowledge_blueprint import BlueprintStatus, KnowledgeBlueprint
from src.services.knowledge.blueprint_embedding_task import (
    get_blueprint_embedding_status,
    rebuild_blueprints_for_kb,
)
from src.services.knowledge.blueprint_generate_service import (
    BlueprintGenerateFailedError,
    BlueprintGenerateTimeoutError,
    NoChildNodesError,
    generate_blueprint_draft,
)
from src.services.knowledge.blueprint_outline_suggest_service import (
    OutlineSuggestFailedError,
    OutlineSuggestTimeoutError,
    suggest_outline,
)
from src.services.knowledge.blueprint_query_parse_service import (
    SearchParseFailedError,
    SearchParseTimeoutError,
    parse_search_query,
)
from src.services.knowledge.blueprint_search_service import (
    BlueprintSearchValidationError,
    search_blueprints,
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
from src.services.knowledge.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/blueprints",
    tags=["blueprints"],
)


def _embed_blueprint_in_background(blueprint_id: UUID) -> None:
    from src.db.session import SessionLocal
    from src.services.knowledge.blueprint_embedding_task import embed_blueprint

    db = SessionLocal()
    try:
        embed_blueprint(db, blueprint_id)
    finally:
        db.close()


def _rebuild_blueprints_in_background(kb_id: UUID) -> None:
    from src.db.session import SessionLocal

    db = SessionLocal()
    try:
        rebuild_blueprints_for_kb(db, kb_id=kb_id)
    finally:
        db.close()


def _serialize_blueprint_item(row: KnowledgeBlueprint, db: Session | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
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
    if db is not None:
        payload["embedding_status"] = get_blueprint_embedding_status(db, row.blueprint_id)
    return payload


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
    except BlueprintGenerateFailedError as exc:
        logger.warning(
            "blueprint generate failed kb_id=%s doc_id=%s node_id=%s reason=%s",
            kb_id,
            body.doc_id,
            body.node_id,
            exc,
        )
        return JSONResponse(
            status_code=502,
            content=error(
                "blueprint_generate_failed",
                "Blueprint generation failed",
                trace_id=get_trace_id(),
            ),
        )
    return success(draft, trace_id=get_trace_id())


@router.post("/suggest-outline")
def suggest_outline_api(
    kb_id: UUID,
    body: SuggestOutlineRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    requirement = body.requirement_description.strip()
    if not requirement:
        return JSONResponse(
            status_code=400,
            content=error(
                "invalid_request",
                "requirement_description is required",
                trace_id=get_trace_id(),
            ),
        )
    if len(requirement) > settings.blueprint_suggest_requirement_max:
        return JSONResponse(
            status_code=400,
            content=error(
                "invalid_request",
                "requirement_description too long",
                trace_id=get_trace_id(),
            ),
        )
    if len(body.blueprint_ids) > settings.blueprint_suggest_max_blueprints:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", "too many blueprint_ids", trace_id=get_trace_id()),
        )

    try:
        result = suggest_outline(
            db,
            kb_id=kb_id,
            blueprint_ids=body.blueprint_ids,
            requirement_description=requirement,
        )
    except BlueprintNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error("blueprint_not_found", "Blueprint not found", trace_id=get_trace_id()),
        )
    except OutlineSuggestTimeoutError:
        return JSONResponse(
            status_code=504,
            content=error("outline_suggest_timeout", "Outline suggest timed out", trace_id=get_trace_id()),
        )
    except OutlineSuggestFailedError as exc:
        message = str(exc)
        if message == "llm not configured":
            return JSONResponse(
                status_code=503,
                content=error("llm_not_configured", "LLM is not configured", trace_id=get_trace_id()),
            )
        if message in {
            "requirement_description empty",
            "requirement_description too long",
            "blueprint_ids empty",
            "too many blueprint_ids",
        }:
            return JSONResponse(
                status_code=400,
                content=error("invalid_request", message, trace_id=get_trace_id()),
            )
        logger.warning("outline suggest failed kb_id=%s reason=%s", kb_id, exc)
        return JSONResponse(
            status_code=502,
            content=error("outline_suggest_failed", "Outline suggest failed", trace_id=get_trace_id()),
        )
    return success(result, trace_id=get_trace_id())


@router.post("/parse-search-query")
def parse_search_query_api(
    kb_id: UUID,
    body: ParseSearchQueryRequest,
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    query = body.query.strip()
    if not query:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", "query is required", trace_id=get_trace_id()),
        )
    if len(query) > settings.blueprint_search_parse_query_max:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", "query too long", trace_id=get_trace_id()),
        )
    try:
        result = parse_search_query(query=query)
    except SearchParseTimeoutError:
        return JSONResponse(
            status_code=504,
            content=error("search_parse_timeout", "Search parse timed out", trace_id=get_trace_id()),
        )
    except SearchParseFailedError as exc:
        message = str(exc)
        if message == "llm not configured":
            return JSONResponse(
                status_code=503,
                content=error("llm_not_configured", "LLM is not configured", trace_id=get_trace_id()),
            )
        if message in {"query empty", "query too long"}:
            return JSONResponse(
                status_code=400,
                content=error("invalid_request", message, trace_id=get_trace_id()),
            )
        logger.warning("search parse failed kb_id=%s reason=%s", kb_id, exc)
        return JSONResponse(
            status_code=502,
            content=error("search_parse_failed", "Search parse failed", trace_id=get_trace_id()),
        )
    return success(result, trace_id=get_trace_id())


@router.post("/search")
def search_blueprints_api(
    kb_id: UUID,
    body: BlueprintSearchRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    semantic = body.semantic_query.strip()
    keyword = body.keyword.strip()
    if not semantic and not keyword:
        return JSONResponse(
            status_code=400,
            content=error(
                "invalid_request",
                "semantic_query and keyword cannot both be empty",
                trace_id=get_trace_id(),
            ),
        )

    query_vector: list[float] | None = None
    if semantic:
        client = EmbeddingClient(model=settings.embedding_model)
        if client.is_configured:
            result = client.embed_text(semantic)
            if result.vector is not None:
                query_vector = result.vector

    try:
        payload = search_blueprints(
            db,
            kb_id=kb_id,
            semantic_query=semantic,
            keyword=keyword,
            product_tags=body.product_tags,
            industry_tags=body.industry_tags,
            scenario_tags=body.scenario_tags,
            vector_weight=body.vector_weight,
            keyword_weight=body.keyword_weight,
            top_k=body.top_k,
            query_vector=query_vector,
        )
    except BlueprintSearchValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", str(exc), trace_id=get_trace_id()),
        )
    return success(payload, trace_id=get_trace_id())


@router.post("/index/rebuild")
def rebuild_blueprint_index_api(
    kb_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    queued = (
        db.query(KnowledgeBlueprint)
        .filter(
            KnowledgeBlueprint.kb_id == kb_id,
            KnowledgeBlueprint.status == BlueprintStatus.active,
        )
        .count()
    )
    background_tasks.add_task(_rebuild_blueprints_in_background, kb_id)
    return success({"queued": queued, "message": "rebuild started"}, trace_id=get_trace_id())


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
    return success(_serialize_blueprint_item(row, db), trace_id=get_trace_id())


@router.post("", status_code=201)
def create_blueprint_api(
    kb_id: UUID,
    body: SaveBlueprintRequest,
    background_tasks: BackgroundTasks,
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
    background_tasks.add_task(_embed_blueprint_in_background, row.blueprint_id)
    return success(_serialize_blueprint_item(row, db), trace_id=get_trace_id())


@router.put("/{blueprint_id}")
def update_blueprint_api(
    kb_id: UUID,
    blueprint_id: UUID,
    body: SaveBlueprintRequest,
    background_tasks: BackgroundTasks,
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
    background_tasks.add_task(_embed_blueprint_in_background, row.blueprint_id)
    return success(_serialize_blueprint_item(row, db), trace_id=get_trace_id())


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
            "items": [_serialize_blueprint_item(item, db) for item in rows],
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
