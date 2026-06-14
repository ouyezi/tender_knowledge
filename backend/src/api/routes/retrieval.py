from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_operator_id, get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.retrieval_trace import RetrievalTraceStatus
from src.schemas.retrieval import (
    OutlineNode,
    RetrievalIntent,
    RetrievalOptions,
    RetrievalRequest,
    ReturnOptions,
    TenderRequirementContext,
)
from src.services.retrieval.retrieval_service import RetrievalService

router = APIRouter(prefix="/api/v1/kbs/{kb_id}/retrieval", tags=["retrieval"])


class DirectoryMatchRequest(BaseModel):
    product_category_ids: list[UUID] = Field(default_factory=list)
    chapter_taxonomy_ids: list[UUID] = Field(default_factory=list)
    tender_requirement_context: TenderRequirementContext = Field(default_factory=TenderRequirementContext)
    outline_nodes: list[OutlineNode] = Field(default_factory=list)
    retrieval_options: RetrievalOptions = Field(default_factory=RetrievalOptions)
    return_options: ReturnOptions = Field(default_factory=ReturnOptions)


class IndexRebuildRequest(BaseModel):
    object_types: list[str] = Field(default_factory=list)
    force_reembed: bool = False


@router.get("/health")
def retrieval_health(
    kb_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _ = (kb_id, db)
    return success({"status": "ok", "scope": "retrieval-foundation"}, trace_id=get_trace_id())


@router.post("/search")
def retrieval_search(
    kb_id: UUID,
    body: RetrievalRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = RetrievalService(db)
    try:
        data = service.search(
            kb_id=kb_id,
            request=body,
            operator_id=get_operator_id(),
        )
    except ValueError as exc:
        if str(exc) == "STRATEGY_VERSION_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content=error(
                    "STRATEGY_VERSION_NOT_FOUND",
                    "strategy version not found",
                    trace_id=get_trace_id(),
                ),
            )
        raise
    db.commit()
    return success(data, trace_id=get_trace_id())


@router.post("/directory-match")
def directory_match(
    kb_id: UUID,
    body: DirectoryMatchRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = RetrievalService(db)
    request = RetrievalRequest(
        query="",
        intent=RetrievalIntent.directory_match,
        product_category_ids=body.product_category_ids,
        chapter_taxonomy_ids=body.chapter_taxonomy_ids,
        tender_requirement_context=body.tender_requirement_context,
        outline_nodes=body.outline_nodes,
        retrieval_options=body.retrieval_options,
        return_options=body.return_options,
    )
    data = service.directory_match(
        kb_id=kb_id,
        request=request,
        operator_id=get_operator_id(),
    )
    db.commit()
    return success(data, trace_id=get_trace_id())


@router.get("/traces")
def list_traces(
    kb_id: UUID,
    intent: RetrievalIntent | None = None,
    status: RetrievalTraceStatus | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    operator_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = RetrievalService(db)
    data = service.list_traces(
        kb_id=kb_id,
        intent=intent,
        status=status,
        from_dt=_parse_dt(from_),
        to_dt=_parse_dt(to),
        operator_id=operator_id,
        page=max(1, page),
        page_size=max(1, min(200, page_size)),
    )
    return success(data, trace_id=get_trace_id())


@router.get("/traces/{trace_id}")
def get_trace_detail(
    kb_id: UUID,
    trace_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    detail = RetrievalService(db).get_trace(kb_id=kb_id, trace_id=trace_id)
    if detail is None:
        return JSONResponse(
            status_code=404,
            content=error("TRACE_NOT_FOUND", "retrieval trace not found", trace_id=get_trace_id()),
        )
    return success(detail, trace_id=get_trace_id())


@router.post("/index/rebuild")
def rebuild_index(
    kb_id: UUID,
    body: IndexRebuildRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    data = RetrievalService(db).rebuild_index(
        kb_id=kb_id,
        object_types=body.object_types,
        force_reembed=body.force_reembed,
    )
    db.commit()
    return success({"task_id": data["task_id"], "status": data["status"]}, trace_id=get_trace_id())


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    return datetime.fromisoformat(text)
