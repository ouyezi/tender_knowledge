from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.deps import get_kb_or_404, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.models.knowledge_base import KnowledgeBase

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/actual-bid-parse",
    tags=["actual-bid-parse"],
)


class TriggerActualBidParseRequest(BaseModel):
    import_id: UUID


@router.get("/tasks")
def list_parse_tasks(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    return success(
        {"items": [], "total": 0, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )


@router.post("/trigger")
def trigger_parse(
    kb_id: UUID,
    body: TriggerActualBidParseRequest,
    _: KnowledgeBase = Depends(kb_write_guard),
):
    _ = body.import_id
    return JSONResponse(
        status_code=501,
        content=error(
            "NOT_IMPLEMENTED",
            "Actual bid parse trigger not implemented yet",
            trace_id=get_trace_id(),
        ),
    )
