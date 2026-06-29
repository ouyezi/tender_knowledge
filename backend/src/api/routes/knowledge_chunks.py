from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.api.schemas.knowledge_chunks import (
    ChunkSearchRequest,
    CreateKnowledgeChunkRequest,
    IndexKnowledgeChunkRequest,
    KnowledgeChunkListFilters,
    ParseChunkSearchQueryRequest,
    PrefillRequest,
)
from src.config import settings
from src.db.session import SessionLocal, get_db
from src.models.chunk_asset import ChunkAsset
from src.models.knowledge_base import KnowledgeBase
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.chunk_index_task import index_knowledge_chunk
from src.services.knowledge.chunk_query_parse_service import (
    SearchParseFailedError,
    SearchParseTimeoutError,
    parse_search_query,
)
from src.services.knowledge.chunk_search_service import (
    ChunkSearchValidationError,
    search_knowledge_chunks,
)
from src.services.knowledge.chunk_service import ChunkConflictError, ChunkNotFoundError, create_knowledge_chunk, delete_knowledge_chunk
from src.services.knowledge.embedding_client import embedding_client_from_settings
from src.services.knowledge.entry_content_service import (
    ContentNotAvailableError,
    DocumentNotFoundError,
    NodeNotFoundError,
    compute_section_char_range,
    get_document_tree,
    get_node_preview,
    knowledge_source_type_for_document,
    list_entry_documents,
)
from src.services.knowledge.media_url_service import (
    load_image_ref_map_payload,
    resolve_storage_path_to_media_url,
)
from src.services.knowledge.prefill_service import prefill_knowledge_attributes
from src.services.knowledge.knowledge_prefill_context import enrich_prefill_metadata
from src.services.knowledge.taxonomy_field_utils import compute_is_expired
from src.services.knowledge.taxonomy_service import expand_business_line_labels, get_taxonomy_label

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/knowledge-chunks",
    tags=["knowledge-chunks"],
)


def _index_chunk_in_background(chunk_id: int) -> None:
    db = SessionLocal()
    try:
        index_knowledge_chunk(db, chunk_id)
    finally:
        db.close()


def _serialize_asset(asset: ChunkAsset, db: Session, *, kb_id: UUID) -> dict:
    image_storage_url = asset.image_storage_url
    if asset.asset_type == "image":
        image_storage_url = resolve_storage_path_to_media_url(
            db,
            kb_id=kb_id,
            storage_path=asset.image_storage_url,
        )
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "asset_code": asset.asset_code,
        "chunk_id": asset.chunk_id,
        "page_start": asset.page_start,
        "page_end": asset.page_end,
        "char_start": asset.char_start,
        "char_end": asset.char_end,
        "raw_markdown": asset.raw_markdown,
        "llm_summary": asset.llm_summary,
        "table_summary": asset.table_summary,
        "table_schema": asset.table_schema,
        "table_headers": asset.table_headers,
        "table_rows": asset.table_rows,
        "table_type": asset.table_type,
        "allow_row_filter": asset.allow_row_filter,
        "image_type": asset.image_type,
        "image_storage_url": image_storage_url,
        "image_caption": asset.image_caption,
        "image_ocr_text": asset.image_ocr_text,
        "extracted_facts": asset.extracted_facts,
        "required_with_text": asset.required_with_text,
        "position_hint": asset.position_hint,
    }


def _enrich_chunk_taxonomy(db: Session, payload: dict, row: KnowledgeChunk) -> dict:
    payload["block_type_code"] = row.block_type_code
    payload["application_type_code"] = row.application_type_code
    payload["business_line_codes"] = list(row.business_line_codes or [])
    payload["block_type_label"] = get_taxonomy_label(db, "block_type", row.block_type_code)
    payload["application_type_label"] = get_taxonomy_label(
        db, "application_type", row.application_type_code
    )
    payload["business_line_labels"] = expand_business_line_labels(
        db, row.business_line_codes or []
    )
    payload["is_expired"] = compute_is_expired(row.expire_date)
    return payload


def _serialize_chunk_list_item(db: Session, row: KnowledgeChunk) -> dict:
    payload = {
        "id": row.id,
        "title": row.title,
        "version": row.version,
        "knowledge_type": row.knowledge_type,
        "status": row.status,
        "embedding_status": row.embedding_status,
        "indexed_at": row.indexed_at.isoformat() if row.indexed_at else None,
        "token_count": row.token_count,
        "update_time": row.update_time.isoformat() if row.update_time else None,
    }
    return _enrich_chunk_taxonomy(db, payload, row)


def _resolve_section_char_range(
    db: Session,
    row: KnowledgeChunk,
) -> tuple[int | None, int | None]:
    if row.char_start is not None:
        return row.char_start, row.char_end
    node_key = str(row.primary_node_id).split("#", 1)[0]
    try:
        node_uuid = UUID(node_key)
    except ValueError:
        return None, None
    return compute_section_char_range(
        db,
        kb_id=row.kb_id,
        doc_id=row.doc_id,
        primary_node_id=node_uuid,
        content=row.content,
    )


def _serialize_chunk_detail(db: Session, row: KnowledgeChunk, *, embedding_status: str) -> dict:
    section_char_start, section_char_end = _resolve_section_char_range(db, row)
    payload = {
        "id": row.id,
        "kb_id": str(row.kb_id),
        "knowledge_code": row.knowledge_code,
        "version": row.version,
        "previous_version_id": row.previous_version_id,
        "is_latest": row.is_latest,
        "title": row.title,
        "content": row.content,
        "summary": row.summary,
        "knowledge_type": row.knowledge_type,
        "content_type": row.content_type,
        "doc_id": str(row.doc_id),
        "file_name": row.file_name,
        "catalog_path": row.catalog_path,
        "primary_node_id": row.primary_node_id,
        "tags": row.tags,
        "regions": row.regions,
        "qualification_info": row.qualification_info,
        "expire_date": row.expire_date.isoformat() if row.expire_date else None,
        "status": row.status,
        "is_template": row.is_template,
        "template_type": row.template_type,
        "security_level": row.security_level,
        "owner": row.owner,
        "review_status": row.review_status,
        "content_hash": row.content_hash,
        "token_count": row.token_count,
        "has_children": row.has_children,
        "children_count": row.children_count,
        "create_time": row.create_time.isoformat() if row.create_time else None,
        "update_time": row.update_time.isoformat() if row.update_time else None,
        "embedding_status": embedding_status,
        "section_char_start": section_char_start,
        "section_char_end": section_char_end,
    }
    return _enrich_chunk_taxonomy(db, payload, row)


def _serialize_previous_version(previous: KnowledgeChunk | None) -> dict | None:
    if previous is None:
        return None
    return {
        "id": previous.id,
        "version": previous.version,
        "title": previous.title,
        "summary": previous.summary,
        "update_time": previous.update_time.isoformat() if previous.update_time else None,
    }


def _contains_any(target_values: list[str], filter_values: list[str] | None) -> bool:
    if not filter_values:
        return True
    target_set = {str(item).strip() for item in (target_values or []) if str(item).strip()}
    return any(value in target_set for value in filter_values)


def _matches_array_filters(row: KnowledgeChunk, filters: KnowledgeChunkListFilters) -> bool:
    return (
        _contains_any(row.business_line_codes or [], filters.business_line_codes)
        and _contains_any(row.regions or [], filters.regions)
        and _contains_any(row.tags or [], filters.tags)
    )


@router.get("/entry/documents")
def list_entry_documents_api(
    kb_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    rows = list_entry_documents(db, kb_id=kb_id)
    return success(
        {
            "items": [
                {
                    "doc_id": str(row.document_id),
                    "document_name": row.document_name,
                    "import_id": str(row.import_id),
                    "source_type": knowledge_source_type_for_document(row),
                    "parse_status": row.parse_status.value,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]
        },
        trace_id=get_trace_id(),
    )


@router.get("/entry/documents/{doc_id}/tree")
def get_document_tree_api(
    kb_id: UUID,
    doc_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        tree = get_document_tree(db, kb_id=kb_id, doc_id=doc_id)
    except DocumentNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error("DOCUMENT_NOT_FOUND", "Document not found", trace_id=get_trace_id()),
        )
    return success({"items": tree}, trace_id=get_trace_id())


@router.get("/entry/documents/{doc_id}/nodes/{node_id}/preview")
def get_node_preview_api(
    kb_id: UUID,
    doc_id: UUID,
    node_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        preview = get_node_preview(db, kb_id=kb_id, doc_id=doc_id, node_id=node_id)
    except DocumentNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error("DOCUMENT_NOT_FOUND", "Document not found", trace_id=get_trace_id()),
        )
    except NodeNotFoundError:
        return JSONResponse(
            status_code=404,
            content=error("NODE_NOT_FOUND", "Node not found", trace_id=get_trace_id()),
        )
    except ContentNotAvailableError:
        return JSONResponse(
            status_code=404,
            content=error(
                "CONTENT_NOT_AVAILABLE",
                "Content not available",
                trace_id=get_trace_id(),
            ),
        )
    return success(preview, trace_id=get_trace_id())


@router.post("/prefill")
def prefill_knowledge_attributes_api(
    kb_id: UUID,
    body: PrefillRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    enriched = enrich_prefill_metadata(
        db,
        kb_id=kb_id,
        doc_id=body.doc_id,
        node_id=body.primary_node_id,
        metadata=body.metadata or {},
    )
    prefill = prefill_knowledge_attributes(content=body.content, metadata=enriched)
    return success(prefill, trace_id=get_trace_id())


@router.post("", status_code=201)
def create_knowledge_chunk_api(
    kb_id: UUID,
    body: CreateKnowledgeChunkRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    payload = body.model_dump(exclude={"doc_id", "primary_node_id", "force"})
    try:
        chunk = create_knowledge_chunk(
            db,
            kb_id=kb_id,
            payload=payload,
            doc_id=body.doc_id,
            primary_node_id=body.primary_node_id,
            force=body.force,
        )
    except ChunkConflictError as exc:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content=error(
                "CHUNK_CONFLICT",
                "Knowledge chunk already exists",
                trace_id=get_trace_id(),
                details={
                    "existing_id": exc.existing_id,
                    "existing_version": exc.existing_version,
                },
            ),
        )

    db.commit()
    return success(
        {
            "id": chunk.id,
            "knowledge_code": chunk.knowledge_code,
            "version": chunk.version,
            "previous_version_id": chunk.previous_version_id,
            "is_latest": chunk.is_latest,
        },
        trace_id=get_trace_id(),
    )


@router.get("")
def list_knowledge_chunks_api(
    kb_id: UUID,
    block_type_code: str | None = None,
    application_type_code: str | None = None,
    business_line_codes: list[str] | None = Query(default=None),
    knowledge_type: str | None = None,
    status: str | None = None,
    regions: list[str] | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    security_level: str | None = None,
    is_template: bool | None = None,
    review_status: str | None = None,
    expire_date_from: date | None = None,
    expire_date_to: date | None = None,
    expired_only: bool | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    filters = KnowledgeChunkListFilters(
        block_type_code=block_type_code,
        application_type_code=application_type_code,
        business_line_codes=business_line_codes,
        knowledge_type=knowledge_type,
        status=status,
        regions=regions,
        tags=tags,
        security_level=security_level,
        is_template=is_template,
        review_status=review_status,
        expire_date_from=expire_date_from,
        expire_date_to=expire_date_to,
        expired_only=expired_only,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    query = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.kb_id == kb_id,
        KnowledgeChunk.is_latest.is_(True),
    )
    if filters.block_type_code:
        query = query.filter(KnowledgeChunk.block_type_code == filters.block_type_code)
    if filters.application_type_code:
        query = query.filter(KnowledgeChunk.application_type_code == filters.application_type_code)
    if filters.knowledge_type:
        query = query.filter(KnowledgeChunk.knowledge_type == filters.knowledge_type)
    if filters.status:
        query = query.filter(KnowledgeChunk.status == filters.status)
    if filters.security_level:
        query = query.filter(KnowledgeChunk.security_level == filters.security_level)
    if filters.is_template is not None:
        query = query.filter(KnowledgeChunk.is_template.is_(filters.is_template))
    if filters.review_status:
        query = query.filter(KnowledgeChunk.review_status == filters.review_status)
    if filters.expire_date_from:
        query = query.filter(KnowledgeChunk.expire_date >= filters.expire_date_from)
    if filters.expire_date_to:
        query = query.filter(KnowledgeChunk.expire_date <= filters.expire_date_to)
    if filters.expired_only is True:
        query = query.filter(
            KnowledgeChunk.expire_date.is_not(None),
            KnowledgeChunk.expire_date < date.today(),
        )
    elif filters.expired_only is False:
        query = query.filter(
            (KnowledgeChunk.expire_date.is_(None))
            | (KnowledgeChunk.expire_date >= date.today())
        )
    if filters.keyword:
        token = f"%{filters.keyword.strip()}%"
        query = query.filter(
            or_(
                KnowledgeChunk.title.ilike(token),
                KnowledgeChunk.summary.ilike(token),
            )
        )

    rows = query.order_by(KnowledgeChunk.update_time.desc()).all()
    rows = [row for row in rows if _matches_array_filters(row, filters)]
    total = len(rows)
    offset = (filters.page - 1) * filters.page_size
    paged = rows[offset : offset + filters.page_size]

    return success(
        {
            "items": [_serialize_chunk_list_item(db, row) for row in paged],
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        },
        trace_id=get_trace_id(),
    )


@router.post("/parse-search-query")
def parse_chunk_search_query_api(
    kb_id: UUID,
    body: ParseChunkSearchQueryRequest,
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _ = kb_id
    query = body.query.strip()
    if not query:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", "query empty", trace_id=get_trace_id()),
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
        logger.warning("chunk search parse failed kb_id=%s reason=%s", kb_id, exc)
        return JSONResponse(
            status_code=502,
            content=error("search_parse_failed", "Search parse failed", trace_id=get_trace_id()),
        )
    return success(result, trace_id=get_trace_id())


@router.post("/search")
def search_knowledge_chunks_api(
    kb_id: UUID,
    body: ChunkSearchRequest,
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
        client = embedding_client_from_settings(model=settings.embedding_model)
        if client.is_configured:
            result = client.embed_text(semantic)
            if result.vector is not None:
                query_vector = result.vector

    try:
        payload = search_knowledge_chunks(
            db,
            kb_id=kb_id,
            semantic_query=semantic,
            keyword=keyword,
            vector_weight=body.vector_weight,
            keyword_weight=body.keyword_weight,
            title_vector_weight=body.title_vector_weight,
            summary_vector_weight=body.summary_vector_weight,
            content_vector_weight=body.content_vector_weight,
            top_k=body.top_k,
            query_vector=query_vector,
        )
    except ChunkSearchValidationError as exc:
        return JSONResponse(
            status_code=400,
            content=error("invalid_request", str(exc), trace_id=get_trace_id()),
        )
    return success(payload, trace_id=get_trace_id())


@router.get("/chunk-assets")
def list_chunk_assets_api(
    kb_id: UUID,
    doc_id: UUID,
    char_start: int | None = None,
    char_end: int | None = None,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    query = db.query(ChunkAsset).filter(
        ChunkAsset.kb_id == kb_id,
        ChunkAsset.doc_id == doc_id,
    )
    if char_start is not None:
        query = query.filter((ChunkAsset.char_end.is_(None)) | (ChunkAsset.char_end > char_start))
    if char_end is not None:
        query = query.filter(
            (ChunkAsset.char_start.is_(None)) | (ChunkAsset.char_start < char_end)
        )
    assets = query.order_by(ChunkAsset.char_start.asc(), ChunkAsset.id.asc()).all()
    return success(
        {"items": [_serialize_asset(asset, db, kb_id=kb_id) for asset in assets]},
        trace_id=get_trace_id(),
    )


@router.post("/{chunk_id}/index")
def index_knowledge_chunk_api(
    kb_id: UUID,
    chunk_id: int,
    body: IndexKnowledgeChunkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _ = body
    row = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.kb_id == kb_id, KnowledgeChunk.id == chunk_id)
        .one_or_none()
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("CHUNK_NOT_FOUND", "Knowledge chunk not found", trace_id=get_trace_id()),
        )
    if row.embedding_status == "indexing":
        return JSONResponse(
            status_code=409,
            content=error("INDEX_IN_PROGRESS", "Index already in progress", trace_id=get_trace_id()),
        )
    row.embedding_status = "indexing"
    db.commit()
    background_tasks.add_task(_index_chunk_in_background, chunk_id)
    return success(
        {"chunk_id": chunk_id, "embedding_status": "indexing"},
        trace_id=get_trace_id(),
    )


@router.delete("/{chunk_id}")
def delete_knowledge_chunk_api(
    kb_id: UUID,
    chunk_id: int,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    try:
        delete_knowledge_chunk(db, kb_id=kb_id, chunk_id=chunk_id)
        db.commit()
    except ChunkNotFoundError:
        db.rollback()
        return JSONResponse(
            status_code=404,
            content=error("CHUNK_NOT_FOUND", "Knowledge chunk not found", trace_id=get_trace_id()),
        )
    return success({"chunk_id": chunk_id, "deleted": True}, trace_id=get_trace_id())


@router.get("/{chunk_id}")
def get_knowledge_chunk_api(
    kb_id: UUID,
    chunk_id: int,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.kb_id == kb_id, KnowledgeChunk.id == chunk_id)
        .one_or_none()
    )
    if row is None:
        return success(None, trace_id=get_trace_id())

    previous = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.kb_id == kb_id, KnowledgeChunk.id == row.previous_version_id)
        .one_or_none()
        if row.previous_version_id is not None
        else None
    )
    assets = (
        db.query(ChunkAsset)
        .filter(ChunkAsset.kb_id == kb_id, ChunkAsset.chunk_id == row.id)
        .order_by(ChunkAsset.char_start.asc(), ChunkAsset.id.asc())
        .all()
    )
    status = row.embedding_status
    payload = _serialize_chunk_detail(db, row, embedding_status=status)
    payload["previous_version"] = _serialize_previous_version(previous)
    payload["assets"] = [_serialize_asset(asset, db, kb_id=kb_id) for asset in assets]
    payload["image_ref_map"] = load_image_ref_map_payload(document_id=row.doc_id)
    return success(payload, trace_id=get_trace_id())

