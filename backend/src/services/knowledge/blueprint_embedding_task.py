from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.models.blueprint_embedding import BlueprintEmbedding
from src.models.knowledge_blueprint import BlueprintStatus, KnowledgeBlueprint
from src.services.knowledge.blueprint_index_text import build_search_text, compute_content_hash
from src.services.knowledge.blueprint_service import get_blueprint_detail
from src.services.knowledge.embedding_client import embedding_client_from_settings

logger = logging.getLogger(__name__)


def _embedding_client():
    return embedding_client_from_settings(model=settings.embedding_model)


def embed_blueprint(db: Session, blueprint_id: UUID) -> str:
    blueprint = db.get(KnowledgeBlueprint, blueprint_id)
    if blueprint is None:
        return "failed"

    detail = get_blueprint_detail(db, kb_id=blueprint.kb_id, blueprint_id=blueprint_id)
    search_text = build_search_text(detail)
    content_hash = compute_content_hash(search_text)

    row = db.get(BlueprintEmbedding, blueprint_id)
    if row is None:
        row = BlueprintEmbedding(
            blueprint_id=blueprint_id,
            kb_id=blueprint.kb_id,
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


def rebuild_blueprints_for_kb(db: Session, *, kb_id: UUID) -> int:
    rows = (
        db.query(KnowledgeBlueprint.blueprint_id)
        .filter(
            KnowledgeBlueprint.kb_id == kb_id,
            KnowledgeBlueprint.status == BlueprintStatus.active,
        )
        .all()
    )
    count = 0
    for (blueprint_id,) in rows:
        embed_blueprint(db, blueprint_id)
        count += 1
    return count


def get_blueprint_embedding_status(db: Session, blueprint_id: UUID) -> str:
    row = db.get(BlueprintEmbedding, blueprint_id)
    if row is None:
        return "pending"
    return row.embedding_status
