from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from e2e.client import ApiClient
from e2e.types import ApiResponse
from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.knowledge_base import KBStatus, KnowledgeBase


def build_kb_name(*, now: datetime | None = None) -> str:
    ts = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"铁建验收-{ts}"


def find_seed_kb_id(db: Session, *, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    row = (
        db.query(KnowledgeBase.kb_id)
        .join(ChapterTaxonomy, ChapterTaxonomy.kb_id == KnowledgeBase.kb_id)
        .filter(KnowledgeBase.status == KBStatus.active)
        .order_by(KnowledgeBase.created_at.asc())
        .first()
    )
    if row is None:
        raise RuntimeError("no active KB with chapter_taxonomies found for clone")
    return str(row[0])


def create_kb_via_api(
    api: ApiClient,
    *,
    clone_from_kb_id: str,
    name: str | None = None,
) -> ApiResponse:
    kb_name = name or build_kb_name()
    return api.request(
        "POST",
        "/api/v1/kbs",
        json_body={"name": kb_name, "clone_from_kb_id": clone_from_kb_id},
    )
