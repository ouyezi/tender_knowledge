from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import settings
from src.models.chunk_asset import ChunkAsset
from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.embedding_client import EmbeddingClient, EmbeddingResult, embedding_client_from_settings

logger = logging.getLogger(__name__)

OBJECT_TYPE_CHUNK = "chunk"
OBJECT_TYPE_ASSET = "asset"


def _embedding_client() -> EmbeddingClient:
    return embedding_client_from_settings(model=settings.embedding_model)


def _get_embedding_row(
    db: Session,
    *,
    object_type: str,
    object_id: int,
) -> ChunkEmbedding | None:
    return (
        db.query(ChunkEmbedding)
        .filter(
            ChunkEmbedding.object_type == object_type,
            ChunkEmbedding.object_id == object_id,
        )
        .one_or_none()
    )


def _upsert_embedding(
    db: Session,
    *,
    object_type: str,
    object_id: int,
    content_text: str,
    summary_text: str | None,
    client: EmbeddingClient,
) -> bool:
    content_result = client.embed_text(content_text)
    summary_result = (
        client.embed_text(summary_text) if summary_text else EmbeddingResult(vector=None)
    )

    row = _get_embedding_row(db, object_type=object_type, object_id=object_id)
    if row is None:
        row = ChunkEmbedding(object_type=object_type, object_id=object_id)
        if _is_sqlite(db):
            row.id = _next_embedding_id(db)
        db.add(row)

    row.content_embedding = content_result.vector
    row.summary_embedding = summary_result.vector if summary_text else None
    db.flush()
    return content_result.vector is not None


def _asset_texts(asset: ChunkAsset) -> tuple[str, str | None]:
    content_parts = [asset.raw_markdown, asset.image_ocr_text]
    content = "\n".join(part for part in content_parts if part).strip()
    summary = asset.llm_summary or asset.table_summary or asset.image_caption
    return content, summary


def embed_knowledge_chunk(db: Session, chunk_id: int) -> str:
    chunk = db.get(KnowledgeChunk, chunk_id)
    if chunk is None:
        return "failed"

    client = _embedding_client()
    if not client.is_configured:
        return "skipped"

    chunk_ok = _upsert_embedding(
        db,
        object_type=OBJECT_TYPE_CHUNK,
        object_id=chunk_id,
        content_text=chunk.content,
        summary_text=chunk.summary,
        client=client,
    )
    if not chunk_ok:
        db.commit()
        return "failed"

    assets = db.query(ChunkAsset).filter(ChunkAsset.chunk_id == chunk_id).all()
    for asset in assets:
        content_text, summary_text = _asset_texts(asset)
        if not content_text and not summary_text:
            continue
        asset_ok = _upsert_embedding(
            db,
            object_type=OBJECT_TYPE_ASSET,
            object_id=asset.id,
            content_text=content_text or summary_text or "",
            summary_text=summary_text,
            client=client,
        )
        if not asset_ok:
            logger.warning(
                "asset embedding failed: chunk_id=%s asset_id=%s",
                chunk_id,
                asset.id,
            )

    db.commit()
    return "ready"


def get_embedding_status(db: Session, chunk_id: int) -> str:
    client = _embedding_client()
    if not client.is_configured:
        return "skipped"

    row = _get_embedding_row(db, object_type=OBJECT_TYPE_CHUNK, object_id=chunk_id)
    if row is None:
        return "pending"
    if row.content_embedding is not None:
        return "ready"
    return "failed"


def _is_sqlite(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "sqlite"


def _next_embedding_id(db: Session) -> int:
    current_max = db.query(func.max(ChunkEmbedding.id)).scalar()
    return int(current_max or 0) + 1
