from uuid import UUID

from fastapi import APIRouter, Depends

from src.api.deps import get_kb_or_404
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.models.knowledge_base import KnowledgeBase

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/bid-outlines",
    tags=["bid-outlines"],
)


@router.get("")
def list_bid_outlines(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    return success(
        {"items": [], "total": 0, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )
