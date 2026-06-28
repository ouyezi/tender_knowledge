from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.models.writing_technique import WritingTechnique
from src.models.writing_technique_embedding import WritingTechniqueEmbedding
from src.services.knowledge.embedding_client import embedding_client_from_settings
from src.services.knowledge.writing_technique_index_text import build_search_text, compute_content_hash
from src.services.knowledge.writing_technique_service import get_technique_detail

logger = logging.getLogger(__name__)


def _embedding_client():
    return embedding_client_from_settings(model=settings.embedding_model)


def _detail_dict(row: WritingTechnique) -> dict[str, object]:
    return {
        "title": row.title,
        "applicable_scene": row.applicable_scene,
        "writing_summary": row.writing_summary,
        "tags": row.tags or [],
        "writing_strategy": row.writing_strategy,
        "must_include": row.must_include,
    }


def embed_writing_technique(db: Session, technique_id: UUID) -> str:
    technique = db.get(WritingTechnique, technique_id)
    if technique is None:
        return "failed"

    detail = get_technique_detail(db, kb_id=technique.kb_id, technique_id=technique_id)
    search_text = build_search_text(_detail_dict(detail))
    content_hash = compute_content_hash(search_text)

    row = db.get(WritingTechniqueEmbedding, technique_id)
    if row is None:
        row = WritingTechniqueEmbedding(
            technique_id=technique_id,
            kb_id=technique.kb_id,
            search_text=search_text,
            embedding_status="pending",
        )
        db.add(row)
    elif row.content_hash == content_hash and row.embedding_status == "ready":
        return "ready"
    else:
        row.search_text = search_text
        row.content_hash = content_hash
        row.embedding_status = "pending"

    client = _embedding_client()
    if not client.is_configured:
        row.embedding_status = "skipped"
        row.indexed_at = datetime.now(timezone.utc)
        db.commit()
        return "skipped"

    result = client.embed_text(search_text)
    if result.vector is None:
        row.embedding_status = "failed"
        row.embedding = None
        row.indexed_at = datetime.now(timezone.utc)
        db.commit()
        return "failed"

    row.embedding = result.vector
    row.embedding_status = "ready"
    row.indexed_at = datetime.now(timezone.utc)
    db.commit()
    return "ready"


def get_writing_technique_embedding_status(db: Session, technique_id: UUID) -> str:
    row = db.get(WritingTechniqueEmbedding, technique_id)
    if row is None:
        return "pending"
    return row.embedding_status
