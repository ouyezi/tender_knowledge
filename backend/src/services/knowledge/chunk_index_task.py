from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import settings
from src.models.chunk_asset import ChunkAsset
from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.chunk_image_assets import ensure_image_assets_for_chunk
from src.services.knowledge.chunk_index_text import build_index_content_hash
from src.services.knowledge.chunk_summary_service import apply_summary_update, rewrite_chunk_summary
from src.services.knowledge.embedding_client import EmbeddingClient, embedding_client_from_settings
from src.services.knowledge.image_extraction_cache_service import compute_file_md5, get_or_create_extraction
from src.services.knowledge.image_vision_service import extract_image, is_core_image_extraction
from src.services.knowledge.media_url_service import resolve_media_reference_to_storage_path

logger = logging.getLogger(__name__)

OBJECT_TYPE_CHUNK = "chunk"


def _embedding_client() -> EmbeddingClient:
    return embedding_client_from_settings(model=settings.embedding_model)


def _resolve_image_path(db: Session, *, kb_id, storage_path: str | None) -> Path | None:
    resolved = resolve_media_reference_to_storage_path(db, kb_id=kb_id, reference=storage_path)
    if not resolved:
        return None
    path = Path(settings.storage_root) / resolved.lstrip("/")
    if path.is_file():
        return path
    logger.warning("image file missing kb_id=%s storage_path=%s abs=%s", kb_id, resolved, path)
    return None


def _get_chunk_embedding_row(db: Session, chunk_id: int) -> ChunkEmbedding | None:
    return (
        db.query(ChunkEmbedding)
        .filter(
            ChunkEmbedding.object_type == OBJECT_TYPE_CHUNK,
            ChunkEmbedding.object_id == chunk_id,
        )
        .one_or_none()
    )


def _upsert_chunk_embeddings(
    db: Session,
    *,
    chunk: KnowledgeChunk,
    client: EmbeddingClient,
) -> bool:
    title_result = client.embed_text(chunk.title)
    summary_result = client.embed_text(chunk.summary or "")
    content_result = client.embed_text(chunk.content)
    if content_result.vector is None:
        return False

    content_hash = build_index_content_hash(
        title=chunk.title,
        summary=chunk.summary,
        content=chunk.content,
    )
    row = _get_chunk_embedding_row(db, chunk.id)
    if row is None:
        row = ChunkEmbedding(object_type=OBJECT_TYPE_CHUNK, object_id=chunk.id)
        if _is_sqlite(db):
            row.id = _next_embedding_id(db)
        db.add(row)

    row.title_embedding = title_result.vector
    row.summary_embedding = summary_result.vector if chunk.summary else None
    row.content_embedding = content_result.vector
    row.content_hash = content_hash
    db.flush()
    return True


def index_knowledge_chunk(db: Session, chunk_id: int) -> str:
    chunk = db.get(KnowledgeChunk, chunk_id)
    if chunk is None:
        return "failed"

    chunk.embedding_status = "indexing"
    db.commit()

    try:
        ensure_image_assets_for_chunk(db, chunk)

        image_assets = (
            db.query(ChunkAsset)
            .filter(
                ChunkAsset.chunk_id == chunk_id,
                ChunkAsset.asset_type == "image",
            )
            .order_by(ChunkAsset.id.asc())
            .limit(settings.knowledge_vision_max_images)
            .all()
        )

        image_context_parts: list[str] = []
        for asset in image_assets:
            image_path = _resolve_image_path(
                db, kb_id=chunk.kb_id, storage_path=asset.image_storage_url
            )
            if image_path is None:
                logger.warning(
                    "skip vision extract chunk_id=%s asset_id=%s image_storage_url=%s",
                    chunk_id,
                    asset.id,
                    asset.image_storage_url,
                )
                continue
            md5_hash = compute_file_md5(image_path)

            def _vision_fn(path: Path = image_path):
                return extract_image(image_path=path)

            extracted = get_or_create_extraction(
                db,
                md5_hash=md5_hash,
                vision_fn=_vision_fn,
                vision_model=settings.knowledge_vision_model,
            )
            asset.image_caption = extracted.get("caption")
            asset.image_ocr_text = extracted.get("ocr_text")
            asset.extracted_facts = extracted.get("extracted_facts")
            if is_core_image_extraction(extracted):
                image_context_parts.append(
                    "\n".join(
                        part
                        for part in (
                            extracted.get("caption"),
                            extracted.get("ocr_text"),
                            str(extracted.get("extracted_facts") or ""),
                        )
                        if part
                    )
                )

        llm_result = rewrite_chunk_summary(
            title=chunk.title,
            content=chunk.content,
            current_summary=chunk.summary,
            image_context="\n\n".join(image_context_parts),
        )
        if llm_result:
            fields, warnings = apply_summary_update(
                current_summary=chunk.summary,
                current_issue_date=chunk.issue_date,
                current_expire_date=chunk.expire_date,
                llm_result=llm_result,
            )
            chunk.summary = fields["summary"]
            chunk.issue_date = fields["issue_date"]
            chunk.expire_date = fields["expire_date"]
            if warnings:
                logger.info("chunk index summary warnings chunk_id=%s warnings=%s", chunk_id, warnings)

        client = _embedding_client()
        if not client.is_configured:
            chunk.embedding_status = "skipped"
            chunk.indexed_at = datetime.now(timezone.utc)
            db.commit()
            return "skipped"

        if not _upsert_chunk_embeddings(db, chunk=chunk, client=client):
            chunk.embedding_status = "failed"
            db.commit()
            return "failed"

        chunk.embedding_status = "ready"
        chunk.indexed_at = datetime.now(timezone.utc)
        db.commit()
        return "ready"
    except Exception:
        logger.exception("chunk index failed chunk_id=%s", chunk_id)
        db.rollback()
        chunk = db.get(KnowledgeChunk, chunk_id)
        if chunk is not None:
            chunk.embedding_status = "failed"
            db.commit()
        return "failed"


def _is_sqlite(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "sqlite"


def _next_embedding_id(db: Session) -> int:
    current_max = db.query(func.max(ChunkEmbedding.id)).scalar()
    return int(current_max or 0) + 1
