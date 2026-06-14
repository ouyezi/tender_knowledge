from datetime import datetime, timezone
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
from src.models.retrieval_eval_case import RetrievalEvalCase, RetrievalEvalCaseCreatedFrom, RetrievalEvalCaseStatus
from src.models.retrieval_eval_set import RetrievalEvalSet
from src.models.retrieval_eval_run import RetrievalEvalRunStatus
from src.models.retrieval_strategy_version import RetrievalStrategyVersion
from src.models.retrieval_trace import RetrievalIntent
from src.services.retrieval.eval import RetrievalEvalRunner

router = APIRouter(prefix="/api/v1/kbs/{kb_id}/retrieval", tags=["retrieval-eval"])


class StrategyCreateRequest(BaseModel):
    name: str
    version_tag: str
    config: dict = Field(default_factory=dict)
    embedding_config_version: str | None = None
    rerank_config_version: str | None = None
    prompt_config_version: str | None = None
    notes: str | None = None


class EvalSetCreateRequest(BaseModel):
    name: str
    description: str | None = None


class EvalCaseCreateRequest(BaseModel):
    query: str
    intent: RetrievalIntent
    filters: dict = Field(default_factory=dict)
    expected_object_ids: list[str] = Field(default_factory=list)
    negative_object_ids: list[str] = Field(default_factory=list)
    product_category_ids: list[str] = Field(default_factory=list)
    chapter_taxonomy_ids: list[str] = Field(default_factory=list)


class EvalCaseConfirmRequest(BaseModel):
    confirmed_by: str


class EvalRunRequest(BaseModel):
    eval_set_id: UUID
    strategy_version_id: UUID
    baseline_strategy_version_id: UUID | None = None
    k: int = 10
    metrics: list[str] = Field(default_factory=list)


@router.get("/strategies")
def list_strategies(
    kb_id: UUID,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    query = db.query(RetrievalStrategyVersion).filter(RetrievalStrategyVersion.kb_id == kb_id)
    if is_active is not None:
        query = query.filter(RetrievalStrategyVersion.is_active.is_(is_active))
    total = query.count()
    rows = (
        query.order_by(RetrievalStrategyVersion.created_at.desc())
        .offset(max(0, page - 1) * page_size)
        .limit(max(1, min(200, page_size)))
        .all()
    )
    return success(
        {
            "items": [_serialize_strategy(row) for row in rows],
            "total": total,
            "page": max(1, page),
            "page_size": max(1, min(200, page_size)),
        },
        trace_id=get_trace_id(),
    )


@router.post("/strategies")
def create_strategy(
    kb_id: UUID,
    body: StrategyCreateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = RetrievalStrategyVersion(
        kb_id=kb_id,
        name=body.name,
        version_tag=body.version_tag,
        config=body.config,
        embedding_config_version=body.embedding_config_version,
        rerank_config_version=body.rerank_config_version,
        prompt_config_version=body.prompt_config_version,
        notes=body.notes,
        is_active=False,
        created_by=get_operator_id(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(_serialize_strategy(row), trace_id=get_trace_id())


@router.post("/strategies/{strategy_version_id}/activate")
def activate_strategy(
    kb_id: UUID,
    strategy_version_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    target = (
        db.query(RetrievalStrategyVersion)
        .filter(
            RetrievalStrategyVersion.kb_id == kb_id,
            RetrievalStrategyVersion.strategy_version_id == strategy_version_id,
        )
        .one_or_none()
    )
    if target is None:
        return JSONResponse(
            status_code=404,
            content=error("STRATEGY_VERSION_NOT_FOUND", "strategy version not found", trace_id=get_trace_id()),
        )
    (
        db.query(RetrievalStrategyVersion)
        .filter(RetrievalStrategyVersion.kb_id == kb_id, RetrievalStrategyVersion.is_active.is_(True))
        .update({"is_active": False}, synchronize_session=False)
    )
    target.is_active = True
    db.commit()
    db.refresh(target)
    return success(_serialize_strategy(target), trace_id=get_trace_id())


@router.get("/eval/sets")
def list_eval_sets(
    kb_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    query = db.query(RetrievalEvalSet).filter(RetrievalEvalSet.kb_id == kb_id)
    total = query.count()
    rows = (
        query.order_by(RetrievalEvalSet.created_at.desc())
        .offset(max(0, page - 1) * page_size)
        .limit(max(1, min(200, page_size)))
        .all()
    )
    return success(
        {
            "items": [_serialize_eval_set(row) for row in rows],
            "total": total,
            "page": max(1, page),
            "page_size": max(1, min(200, page_size)),
        },
        trace_id=get_trace_id(),
    )


@router.post("/eval/sets")
def create_eval_set(
    kb_id: UUID,
    body: EvalSetCreateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = RetrievalEvalSet(
        kb_id=kb_id,
        name=body.name,
        description=body.description,
        created_by=get_operator_id(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(_serialize_eval_set(row), trace_id=get_trace_id())


@router.get("/eval/sets/{eval_set_id}/cases")
def list_eval_cases(
    kb_id: UUID,
    eval_set_id: UUID,
    status: RetrievalEvalCaseStatus | None = None,
    created_from: RetrievalEvalCaseCreatedFrom | None = Query(default=None, alias="created_from"),
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    query = db.query(RetrievalEvalCase).filter(
        RetrievalEvalCase.kb_id == kb_id,
        RetrievalEvalCase.eval_set_id == eval_set_id,
    )
    if status is not None:
        query = query.filter(RetrievalEvalCase.status == status)
    if created_from is not None:
        query = query.filter(RetrievalEvalCase.created_from == created_from)
    total = query.count()
    rows = (
        query.order_by(RetrievalEvalCase.created_at.desc())
        .offset(max(0, page - 1) * page_size)
        .limit(max(1, min(200, page_size)))
        .all()
    )
    return success(
        {
            "items": [_serialize_eval_case(row) for row in rows],
            "total": total,
            "page": max(1, page),
            "page_size": max(1, min(200, page_size)),
        },
        trace_id=get_trace_id(),
    )


@router.post("/eval/sets/{eval_set_id}/cases")
def create_eval_case(
    kb_id: UUID,
    eval_set_id: UUID,
    body: EvalCaseCreateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = RetrievalEvalCase(
        eval_set_id=eval_set_id,
        kb_id=kb_id,
        query=body.query,
        intent=body.intent,
        filters=body.filters,
        expected_object_ids=body.expected_object_ids,
        negative_object_ids=body.negative_object_ids,
        product_category_ids=body.product_category_ids,
        chapter_taxonomy_ids=body.chapter_taxonomy_ids,
        created_from=RetrievalEvalCaseCreatedFrom.manual,
        status=RetrievalEvalCaseStatus.pending,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return success(_serialize_eval_case(row), trace_id=get_trace_id())


@router.post("/eval/cases/{eval_case_id}/confirm")
def confirm_eval_case(
    kb_id: UUID,
    eval_case_id: UUID,
    body: EvalCaseConfirmRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(RetrievalEvalCase)
        .filter(RetrievalEvalCase.kb_id == kb_id, RetrievalEvalCase.eval_case_id == eval_case_id)
        .one_or_none()
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("EVAL_CASE_NOT_FOUND", "eval case not found", trace_id=get_trace_id()),
        )
    row.status = RetrievalEvalCaseStatus.confirmed
    row.confirmed_by = body.confirmed_by
    row.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return success(_serialize_eval_case(row), trace_id=get_trace_id())


@router.post("/eval/cases/{eval_case_id}/reject")
def reject_eval_case(
    kb_id: UUID,
    eval_case_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = (
        db.query(RetrievalEvalCase)
        .filter(RetrievalEvalCase.kb_id == kb_id, RetrievalEvalCase.eval_case_id == eval_case_id)
        .one_or_none()
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("EVAL_CASE_NOT_FOUND", "eval case not found", trace_id=get_trace_id()),
        )
    row.status = RetrievalEvalCaseStatus.rejected
    row.confirmed_by = None
    row.confirmed_at = None
    db.commit()
    db.refresh(row)
    return success(_serialize_eval_case(row), trace_id=get_trace_id())


@router.post("/eval/runs")
def create_eval_run(
    kb_id: UUID,
    body: EvalRunRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    service = RetrievalEvalRunner(db)
    try:
        run = service.run(
            kb_id=kb_id,
            eval_set_id=body.eval_set_id,
            strategy_version_id=body.strategy_version_id,
            baseline_strategy_version_id=body.baseline_strategy_version_id,
            k=body.k,
            metrics=body.metrics,
            triggered_by=get_operator_id(),
        )
    except ValueError as exc:
        code = str(exc)
        if code == "STRATEGY_VERSION_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content=error("STRATEGY_VERSION_NOT_FOUND", "strategy version not found", trace_id=get_trace_id()),
            )
        if code == "EVAL_SET_NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content=error("EVAL_SET_NOT_FOUND", "eval set not found", trace_id=get_trace_id()),
            )
        if code == "EVAL_SET_EMPTY":
            return JSONResponse(
                status_code=422,
                content=error("EVAL_SET_EMPTY", "no confirmed eval cases", trace_id=get_trace_id()),
            )
        if code == "EVAL_RUN_IN_PROGRESS":
            return JSONResponse(
                status_code=409,
                content=error("EVAL_RUN_IN_PROGRESS", "eval run in progress", trace_id=get_trace_id()),
            )
        raise
    db.commit()
    return success(_serialize_eval_run(run), trace_id=get_trace_id())


@router.get("/eval/runs/{eval_run_id}")
def get_eval_run(
    kb_id: UUID,
    eval_run_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = RetrievalEvalRunner(db).get_run(kb_id=kb_id, eval_run_id=eval_run_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("EVAL_RUN_NOT_FOUND", "eval run not found", trace_id=get_trace_id()),
        )
    return success(_serialize_eval_run(row), trace_id=get_trace_id())


def _serialize_strategy(row: RetrievalStrategyVersion) -> dict:
    return {
        "strategy_version_id": str(row.strategy_version_id),
        "name": row.name,
        "version_tag": row.version_tag,
        "config": row.config or {},
        "embedding_config_version": row.embedding_config_version,
        "rerank_config_version": row.rerank_config_version,
        "prompt_config_version": row.prompt_config_version,
        "notes": row.notes,
        "is_active": row.is_active,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
    }


def _serialize_eval_set(row: RetrievalEvalSet) -> dict:
    return {
        "eval_set_id": str(row.eval_set_id),
        "name": row.name,
        "description": row.description,
        "status": row.status.value,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_eval_case(row: RetrievalEvalCase) -> dict:
    return {
        "eval_case_id": str(row.eval_case_id),
        "eval_set_id": str(row.eval_set_id),
        "query": row.query,
        "intent": row.intent.value,
        "filters": row.filters or {},
        "expected_object_ids": row.expected_object_ids or [],
        "negative_object_ids": row.negative_object_ids or [],
        "product_category_ids": row.product_category_ids or [],
        "chapter_taxonomy_ids": row.chapter_taxonomy_ids or [],
        "created_from": row.created_from.value,
        "source_feedback_id": str(row.source_feedback_id) if row.source_feedback_id else None,
        "status": row.status.value,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
        "confirmed_by": row.confirmed_by,
        "created_at": row.created_at.isoformat(),
    }


def _serialize_eval_run(row) -> dict:
    return {
        "eval_run_id": str(row.eval_run_id),
        "status": row.status.value if isinstance(row.status, RetrievalEvalRunStatus) else str(row.status),
        "eval_set_id": str(row.eval_set_id),
        "strategy_version_id": str(row.strategy_version_id),
        "baseline_strategy_version_id": str(row.baseline_strategy_version_id)
        if row.baseline_strategy_version_id
        else None,
        "metrics": row.metrics,
        "comparison_metrics": row.comparison_metrics,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "triggered_by": row.triggered_by,
    }
