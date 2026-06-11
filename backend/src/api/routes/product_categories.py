from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.product_category import CategoryStatus
from src.services.alias_registry import AliasConflictError
from src.models.classification_reference import ClassificationType
from src.services import impact_analysis, product_category_service as svc
from src.services.merge_service import MergeError, merge_product_category
from src.services.product_category_service import InvalidStateError, ValidationError

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/product-categories",
    tags=["product-categories"],
)


class CreateCategoryRequest(BaseModel):
    parent_id: UUID | None = None
    category_name: str
    category_code: str
    description: str | None = None
    aliases: list[str] = []


class PatchCategoryRequest(BaseModel):
    category_name: str | None = None
    description: str | None = None
    status: str | None = None


class ReplaceAliasesRequest(BaseModel):
    aliases: list[str]


class MergeCategoryRequest(BaseModel):
    target_category_id: UUID


def _conflict_response(exc: AliasConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=error(
            "CONFLICT",
            str(exc),
            trace_id=get_trace_id(),
            details={"field": exc.field, "value": exc.value},
        ),
    )


def _invalid_state_response(exc: InvalidStateError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=error(
            exc.code,
            str(exc),
            trace_id=get_trace_id(),
        ),
    )


def _merge_error_response(exc: MergeError) -> JSONResponse:
    status = 409 if exc.code != "VALIDATION" else 400
    return JSONResponse(
        status_code=status,
        content=error(exc.code, str(exc), trace_id=get_trace_id()),
    )


def _validation_response(exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error(
            exc.code,
            str(exc),
            trace_id=get_trace_id(),
        ),
    )


def _get_category_or_404(db: Session, kb_id: UUID, category_id: UUID):
    cat = svc.get_category(db, kb_id, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.get("/tree")
def get_tree(
    kb_id: UUID,
    status: str = "active",
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    st = CategoryStatus(status) if status and not include_inactive else None
    categories = svc.list_categories(
        db, kb_id, status=st, include_inactive=include_inactive
    )
    return success(
        {"nodes": svc.build_tree_nodes(categories)},
        trace_id=get_trace_id(),
    )


@router.get("/search")
def search_categories(
    kb_id: UUID,
    q: str,
    limit: int = 20,
    status: str = "active",
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    items = svc.search_categories(
        db,
        kb_id,
        q=q,
        limit=limit,
        status=CategoryStatus(status),
    )
    return success({"items": items}, trace_id=get_trace_id())


@router.post("")
def create_category(
    kb_id: UUID,
    body: CreateCategoryRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    try:
        cat = svc.create_category(
            db,
            kb_id,
            category_name=body.category_name,
            category_code=body.category_code,
            parent_id=body.parent_id,
            description=body.description,
            aliases=body.aliases,
        )
    except AliasConflictError as exc:
        return _conflict_response(exc)
    except ValidationError as exc:
        return _validation_response(exc)

    return success(
        {
            "category_id": str(cat.category_id),
            "category_name": cat.category_name,
            "category_code": cat.category_code,
            "status": cat.status.value,
            "depth": cat.depth,
            "aliases": [a.alias for a in cat.aliases],
        },
        trace_id=get_trace_id(),
    )


@router.get("/{category_id}")
def get_category_detail(
    kb_id: UUID,
    category_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    detail = svc.get_category_detail(db, kb_id, category_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return success(detail, trace_id=get_trace_id())


@router.patch("/{category_id}")
def patch_category(
    kb_id: UUID,
    category_id: UUID,
    body: PatchCategoryRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    cat = _get_category_or_404(db, kb_id, category_id)
    status = CategoryStatus(body.status) if body.status else None
    try:
        cat = svc.update_category(
            db,
            cat,
            category_name=body.category_name,
            description=body.description,
            status=status,
        )
    except AliasConflictError as exc:
        return _conflict_response(exc)
    except InvalidStateError as exc:
        return _invalid_state_response(exc)

    return success(
        {
            "category_id": str(cat.category_id),
            "category_name": cat.category_name,
            "status": cat.status.value,
        },
        trace_id=get_trace_id(),
    )


@router.put("/{category_id}/aliases")
def put_aliases(
    kb_id: UUID,
    category_id: UUID,
    body: ReplaceAliasesRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    cat = _get_category_or_404(db, kb_id, category_id)
    try:
        cat = svc.replace_aliases(db, cat, body.aliases)
    except AliasConflictError as exc:
        return _conflict_response(exc)

    return success(
        {"category_id": str(cat.category_id), "aliases": [a.alias for a in cat.aliases]},
        trace_id=get_trace_id(),
    )


@router.get("/{category_id}/impact")
def get_category_impact(
    kb_id: UUID,
    category_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _get_category_or_404(db, kb_id, category_id)
    report = impact_analysis.get_report(
        db,
        kb_id,
        ClassificationType.product_category,
        category_id,
    )
    return success(report, trace_id=get_trace_id())


@router.post("/{category_id}/merge")
def merge_category(
    kb_id: UUID,
    category_id: UUID,
    body: MergeCategoryRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    source = _get_category_or_404(db, kb_id, category_id)
    target = _get_category_or_404(db, kb_id, body.target_category_id)
    try:
        result = merge_product_category(
            db,
            source,
            target,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
    except MergeError as exc:
        return _merge_error_response(exc)
    return success(result, trace_id=get_trace_id())


@router.post("/{category_id}/deactivate")
def deactivate_category(
    kb_id: UUID,
    category_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    cat = _get_category_or_404(db, kb_id, category_id)
    try:
        cat = svc.deactivate_category(db, cat)
    except InvalidStateError as exc:
        return _invalid_state_response(exc)

    return success(
        {"category_id": str(cat.category_id), "status": cat.status.value},
        trace_id=get_trace_id(),
    )


@router.post("/{category_id}/archive")
def archive_category(
    kb_id: UUID,
    category_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    cat = _get_category_or_404(db, kb_id, category_id)
    cat = svc.archive_category(db, cat)
    return success(
        {"category_id": str(cat.category_id), "status": cat.status.value},
        trace_id=get_trace_id(),
    )
