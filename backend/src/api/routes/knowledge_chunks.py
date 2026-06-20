from __future__ import annotations

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
    CreateKnowledgeChunkRequest,
    KnowledgeChunkListFilters,
    PrefillRequest,
)
from src.db.session import SessionLocal, get_db
from src.models.chunk_asset import ChunkAsset
from src.models.knowledge_base import KnowledgeBase
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge_v2.chunk_service import ChunkConflictError, create_knowledge_chunk
from src.services.knowledge_v2.embedding_task import embed_knowledge_chunk, get_embedding_status
from src.services.knowledge_v2.entry_content_service import (
    ContentNotAvailableError,
    DocumentNotFoundError,
    NodeNotFoundError,
    get_document_tree,
    get_node_preview,
    knowledge_source_type_for_document,
    list_entry_documents,
)
from src.services.knowledge_v2.media_url_service import (
    load_image_ref_map_payload,
    resolve_storage_path_to_media_url,
)
from src.services.knowledge_v2.prefill_service import prefill_knowledge_attributes

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/knowledge-chunks",
    tags=["knowledge-chunks"],
)


def _embed_chunk_in_background(chunk_id: int) -> None:
    db = SessionLocal()
    try:
        embed_knowledge_chunk(db, chunk_id)
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
        "image_storage_url": asset.image_storage_url,
        "image_caption": asset.image_caption,
        "image_ocr_text": asset.image_ocr_text,
        "required_with_text": asset.required_with_text,
        "position_hint": asset.position_hint,
    }


def _serialize_chunk_list_item(row: KnowledgeChunk) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "version": row.version,
        "category": row.category,
        "knowledge_type": row.knowledge_type,
        "status": row.status,
        "token_count": row.token_count,
        "update_time": row.update_time.isoformat() if row.update_time else None,
    }


def _serialize_chunk_detail(row: KnowledgeChunk, *, embedding_status: str) -> dict:
    return {
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
        "source_type": row.source_type,
        "project_name": row.project_name,
        "page_start": row.page_start,
        "page_end": row.page_end,
        "char_start": row.char_start,
        "char_end": row.char_end,
        "catalog_path": row.catalog_path,
        "primary_node_id": row.primary_node_id,
        "parent_id": row.parent_id,
        "need_parent_context": row.need_parent_context,
        "quote_mode": row.quote_mode,
        "category": row.category,
        "tags": row.tags,
        "products": row.products,
        "industries": row.industries,
        "customer_types": row.customer_types,
        "regions": row.regions,
        "issue_date": row.issue_date.isoformat() if row.issue_date else None,
        "expire_date": row.expire_date.isoformat() if row.expire_date else None,
        "status": row.status,
        "is_template": row.is_template,
        "template_type": row.template_type,
        "variables": row.variables,
        "is_immutable": row.is_immutable,
        "exclusion_rules": row.exclusion_rules,
        "retrieval_weight": float(row.retrieval_weight),
        "security_level": row.security_level,
        "owner": row.owner,
        "review_status": row.review_status,
        "winning_flag": row.winning_flag,
        "edit_distance_avg": row.edit_distance_avg,
        "content_hash": row.content_hash,
        "token_count": row.token_count,
        "has_children": row.has_children,
        "children_count": row.children_count,
        "create_time": row.create_time.isoformat() if row.create_time else None,
        "update_time": row.update_time.isoformat() if row.update_time else None,
        "embedding_status": embedding_status,
    }


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
        _contains_any(row.products or [], filters.products)
        and _contains_any(row.industries or [], filters.industries)
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
    _ = db
    _ = kb_id
    prefill = prefill_knowledge_attributes(content=body.content, metadata=body.metadata or {})
    return success(prefill, trace_id=get_trace_id())


@router.post("", status_code=201)
def create_knowledge_chunk_api(
    kb_id: UUID,
    body: CreateKnowledgeChunkRequest,
    background_tasks: BackgroundTasks,
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
    background_tasks.add_task(_embed_chunk_in_background, chunk.id)
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
    category: str | None = None,
    knowledge_type: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    products: list[str] | None = Query(default=None),
    industries: list[str] | None = Query(default=None),
    regions: list[str] | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    security_level: str | None = None,
    is_template: bool | None = None,
    winning_flag: bool | None = None,
    review_status: str | None = None,
    issue_date_from: date | None = None,
    issue_date_to: date | None = None,
    expire_date_from: date | None = None,
    expire_date_to: date | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    filters = KnowledgeChunkListFilters(
        category=category,
        knowledge_type=knowledge_type,
        source_type=source_type,
        status=status,
        products=products,
        industries=industries,
        regions=regions,
        tags=tags,
        security_level=security_level,
        is_template=is_template,
        winning_flag=winning_flag,
        review_status=review_status,
        issue_date_from=issue_date_from,
        issue_date_to=issue_date_to,
        expire_date_from=expire_date_from,
        expire_date_to=expire_date_to,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    query = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.kb_id == kb_id,
        KnowledgeChunk.is_latest.is_(True),
    )
    if filters.category:
        query = query.filter(KnowledgeChunk.category == filters.category)
    if filters.knowledge_type:
        query = query.filter(KnowledgeChunk.knowledge_type == filters.knowledge_type)
    if filters.source_type:
        query = query.filter(KnowledgeChunk.source_type == filters.source_type)
    if filters.status:
        query = query.filter(KnowledgeChunk.status == filters.status)
    if filters.security_level:
        query = query.filter(KnowledgeChunk.security_level == filters.security_level)
    if filters.is_template is not None:
        query = query.filter(KnowledgeChunk.is_template.is_(filters.is_template))
    if filters.winning_flag is not None:
        query = query.filter(KnowledgeChunk.winning_flag.is_(filters.winning_flag))
    if filters.review_status:
        query = query.filter(KnowledgeChunk.review_status == filters.review_status)
    if filters.issue_date_from:
        query = query.filter(KnowledgeChunk.issue_date >= filters.issue_date_from)
    if filters.issue_date_to:
        query = query.filter(KnowledgeChunk.issue_date <= filters.issue_date_to)
    if filters.expire_date_from:
        query = query.filter(KnowledgeChunk.expire_date >= filters.expire_date_from)
    if filters.expire_date_to:
        query = query.filter(KnowledgeChunk.expire_date <= filters.expire_date_to)
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
            "items": [_serialize_chunk_list_item(row) for row in paged],
            "total": total,
            "page": filters.page,
            "page_size": filters.page_size,
        },
        trace_id=get_trace_id(),
    )


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
    status = get_embedding_status(db, row.id)
    payload = _serialize_chunk_detail(row, embedding_status=status)
    payload["previous_version"] = _serialize_previous_version(previous)
    payload["assets"] = [_serialize_asset(asset, db, kb_id=kb_id) for asset in assets]
    payload["image_ref_map"] = load_image_ref_map_payload(document_id=row.doc_id)
    return success(payload, trace_id=get_trace_id())

