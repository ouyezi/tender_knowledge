from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.api.schemas.knowledge_taxonomy import KnowledgeTaxonomyItem
from src.db.session import get_db
from src.models.knowledge_taxonomy import KnowledgeTaxonomy
from src.services.knowledge.taxonomy_service import list_taxonomy

router = APIRouter(prefix="/api/v1/knowledge-taxonomy", tags=["knowledge-taxonomy"])


def _serialize(row: KnowledgeTaxonomy) -> dict:
    return KnowledgeTaxonomyItem(
        code=row.code,
        dimension=row.dimension,
        parent_code=row.parent_code,
        label=row.label,
        label_en=row.label_en,
        level=row.level,
        sort_order=row.sort_order,
        is_active=row.is_active,
    ).model_dump()


@router.get("")
def list_taxonomy_api(
    dimension: str | None = Query(default=None),
    parent_code: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    rows = list_taxonomy(
        db,
        dimension=dimension,
        parent_code=parent_code,
        active_only=active_only,
    )
    return success({"items": [_serialize(row) for row in rows]}, trace_id=get_trace_id())


@router.get("/{code}")
def get_taxonomy_item_api(code: str, db: Session = Depends(get_db)):
    match = next((row for row in list_taxonomy(db, active_only=True) if row.code == code), None)
    if match is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "taxonomy item not found", trace_id=get_trace_id()),
        )
    return success(_serialize(match), trace_id=get_trace_id())
