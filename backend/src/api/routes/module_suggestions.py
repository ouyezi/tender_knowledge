from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404
from src.api.envelope import error, success
from src.api.middleware.audit import get_operator_id, get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.schemas.retrieval import (
    OutlineNode,
    RetrievalIntent,
    RetrievalOptions,
    RetrievalRequest,
    ReturnOptions,
    TenderRequirementContext,
)
from src.services.retrieval.module_suggestion.module_suggestion_service import ModuleSuggestionService

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/module-suggestions",
    tags=["module-suggestions"],
)


class ModuleSuggestionRequest(BaseModel):
    product_category_ids: list[UUID] = Field(default_factory=list)
    project_type: str | None = None
    customer_type: str | None = None
    requirement_text: str = ""
    tender_requirement_context: TenderRequirementContext = Field(default_factory=TenderRequirementContext)
    outline_nodes: list[OutlineNode] = Field(default_factory=list)
    retrieval_options: RetrievalOptions = Field(default_factory=RetrievalOptions)
    return_options: ReturnOptions = Field(default_factory=ReturnOptions)


@router.post("")
def create_module_suggestion(
    kb_id: UUID,
    body: ModuleSuggestionRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    if not body.outline_nodes:
        return JSONResponse(status_code=422, content=error("EMPTY_OUTLINE", "outline_nodes cannot be empty", trace_id=get_trace_id()))
    request = RetrievalRequest(
        query=body.requirement_text,
        intent=RetrievalIntent.module_suggestion,
        product_category_ids=body.product_category_ids,
        tender_requirement_context=body.tender_requirement_context,
        outline_nodes=body.outline_nodes,
        retrieval_options=body.retrieval_options,
        return_options=body.return_options,
    )
    data = ModuleSuggestionService(db).create_suggestions(
        kb_id=kb_id,
        request=request,
        operator_id=get_operator_id(),
    )
    db.commit()
    return success(data, trace_id=get_trace_id())


@router.get("/{suggestion_id}")
def get_module_suggestion(
    kb_id: UUID,
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    suggestion = ModuleSuggestionService(db).get_suggestion(kb_id=kb_id, suggestion_id=suggestion_id)
    if suggestion is None:
        return JSONResponse(
            status_code=404,
            content=error("SUGGESTION_NOT_FOUND", "module suggestion not found", trace_id=get_trace_id()),
        )
    return success(
        {
            "suggestion_id": str(suggestion.suggestion_id),
            "trace_id": str(suggestion.trace_id),
            "target_outline_node": suggestion.target_outline_node,
            "suggested_template_chapter_ids": suggestion.suggested_template_chapter_ids,
            "suggested_ku_ids": suggestion.suggested_ku_ids,
            "suggested_wiki_ids": suggestion.suggested_wiki_ids,
            "suggested_manual_asset_ids": suggestion.suggested_manual_asset_ids,
            "suggested_bid_outline_node_ids": suggestion.suggested_bid_outline_node_ids,
            "suggested_chapter_pattern_ids": suggestion.suggested_chapter_pattern_ids,
            "organization_hint": suggestion.organization_hint,
            "match_score": suggestion.match_score,
            "coverage_rate": suggestion.coverage_rate,
            "score_detail": suggestion.score_detail,
            "score_point_coverage": suggestion.score_point_coverage,
            "rejection_risks": suggestion.rejection_risks,
            "risk_flags": suggestion.risk_flags,
            "hit_reason": suggestion.hit_reason,
            "knowledge_pack_snapshot": suggestion.knowledge_pack_snapshot,
            "created_at": suggestion.created_at.isoformat(),
        },
        trace_id=get_trace_id(),
    )
