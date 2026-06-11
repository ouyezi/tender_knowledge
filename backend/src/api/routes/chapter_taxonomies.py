from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.chapter_taxonomy import BindingSource
from src.models.knowledge_base import KnowledgeBase
from src.models.product_category import CategoryStatus
from src.services.alias_registry import AliasConflictError
from src.models.classification_reference import ClassificationType
from src.services import chapter_taxonomy_service as svc, impact_analysis
from src.services.merge_service import MergeError, merge_chapter_taxonomy
from src.services.product_category_service import InvalidStateError, ValidationError

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/chapter-taxonomies",
    tags=["chapter-taxonomies"],
)


class CreateTaxonomyRequest(BaseModel):
    parent_id: UUID | None = None
    standard_name: str
    taxonomy_code: str
    description: str | None = None
    synonyms: list[str] = []
    product_category_ids: list[UUID] = []


class PatchTaxonomyRequest(BaseModel):
    standard_name: str | None = None
    description: str | None = None
    status: str | None = None


class ReplaceSynonymsRequest(BaseModel):
    synonyms: list[str]


class ReplaceBindingsRequest(BaseModel):
    product_category_ids: list[UUID]
    source: str = "manual"


class MergeTaxonomyRequest(BaseModel):
    target_taxonomy_id: UUID


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
        content=error(exc.code, str(exc), trace_id=get_trace_id()),
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
        content=error(exc.code, str(exc), trace_id=get_trace_id()),
    )


def _get_taxonomy_or_404(db: Session, kb_id: UUID, taxonomy_id: UUID):
    tax = svc.get_taxonomy(db, kb_id, taxonomy_id)
    if tax is None:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    return tax


@router.get("")
def list_taxonomies(
    kb_id: UUID,
    product_category_id: UUID | None = None,
    status: str = "active",
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    items = svc.list_taxonomies(
        db,
        kb_id,
        status=CategoryStatus(status),
        product_category_id=product_category_id,
    )
    return success(
        {
            "items": [
                {
                    "taxonomy_id": str(t.taxonomy_id),
                    "standard_name": t.standard_name,
                    "taxonomy_code": t.taxonomy_code,
                    "status": t.status.value,
                    "product_category_ids": [str(b.category_id) for b in t.bindings],
                }
                for t in items
            ]
        },
        trace_id=get_trace_id(),
    )


@router.get("/tree")
def get_tree(
    kb_id: UUID,
    status: str = "active",
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    st = CategoryStatus(status) if status and not include_inactive else None
    taxonomies = svc.list_taxonomies(
        db, kb_id, status=st, include_inactive=include_inactive
    )
    return success(
        {"nodes": svc.build_tree_nodes(taxonomies)},
        trace_id=get_trace_id(),
    )


@router.get("/search")
def search_taxonomies(
    kb_id: UUID,
    q: str,
    limit: int = 20,
    status: str = "active",
    product_category_id: UUID | None = None,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    items = svc.search_taxonomies(
        db,
        kb_id,
        q=q,
        limit=limit,
        status=CategoryStatus(status),
        product_category_id=product_category_id,
    )
    return success({"items": items}, trace_id=get_trace_id())


@router.post("")
def create_taxonomy(
    kb_id: UUID,
    body: CreateTaxonomyRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        tax = svc.create_taxonomy(
            db,
            kb_id,
            standard_name=body.standard_name,
            taxonomy_code=body.taxonomy_code,
            parent_id=body.parent_id,
            description=body.description,
            synonyms=body.synonyms,
            product_category_ids=body.product_category_ids,
            operator_id=operator_id,
        )
    except AliasConflictError as exc:
        return _conflict_response(exc)
    except ValidationError as exc:
        return _validation_response(exc)

    return success(
        {
            "taxonomy_id": str(tax.taxonomy_id),
            "standard_name": tax.standard_name,
            "taxonomy_code": tax.taxonomy_code,
            "status": tax.status.value,
            "synonyms": [s.synonym for s in tax.synonyms],
            "product_category_ids": [str(b.category_id) for b in tax.bindings],
        },
        trace_id=get_trace_id(),
    )


@router.get("/{taxonomy_id}")
def get_taxonomy_detail(
    kb_id: UUID,
    taxonomy_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    detail = svc.get_taxonomy_detail(db, kb_id, taxonomy_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    return success(detail, trace_id=get_trace_id())


@router.patch("/{taxonomy_id}")
def patch_taxonomy(
    kb_id: UUID,
    taxonomy_id: UUID,
    body: PatchTaxonomyRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    tax = _get_taxonomy_or_404(db, kb_id, taxonomy_id)
    status = CategoryStatus(body.status) if body.status else None
    try:
        tax = svc.update_taxonomy(
            db,
            tax,
            standard_name=body.standard_name,
            description=body.description,
            status=status,
        )
    except AliasConflictError as exc:
        return _conflict_response(exc)
    except InvalidStateError as exc:
        return _invalid_state_response(exc)

    return success(
        {
            "taxonomy_id": str(tax.taxonomy_id),
            "standard_name": tax.standard_name,
            "status": tax.status.value,
        },
        trace_id=get_trace_id(),
    )


@router.put("/{taxonomy_id}/synonyms")
def put_synonyms(
    kb_id: UUID,
    taxonomy_id: UUID,
    body: ReplaceSynonymsRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    tax = _get_taxonomy_or_404(db, kb_id, taxonomy_id)
    try:
        tax = svc.replace_synonyms(db, tax, body.synonyms)
    except AliasConflictError as exc:
        return _conflict_response(exc)

    return success(
        {"taxonomy_id": str(tax.taxonomy_id), "synonyms": [s.synonym for s in tax.synonyms]},
        trace_id=get_trace_id(),
    )


@router.put("/{taxonomy_id}/product-categories")
def put_product_categories(
    kb_id: UUID,
    taxonomy_id: UUID,
    body: ReplaceBindingsRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    tax = _get_taxonomy_or_404(db, kb_id, taxonomy_id)
    try:
        tax = svc.replace_product_category_bindings(
            db,
            tax,
            body.product_category_ids,
            source=BindingSource(body.source),
            operator_id=operator_id,
        )
    except ValidationError as exc:
        return _validation_response(exc)

    return success(
        {
            "taxonomy_id": str(tax.taxonomy_id),
            "product_category_ids": [str(b.category_id) for b in tax.bindings],
        },
        trace_id=get_trace_id(),
    )


@router.get("/{taxonomy_id}/impact")
def get_taxonomy_impact(
    kb_id: UUID,
    taxonomy_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _get_taxonomy_or_404(db, kb_id, taxonomy_id)
    report = impact_analysis.get_report(
        db,
        kb_id,
        ClassificationType.chapter_taxonomy,
        taxonomy_id,
    )
    return success(report, trace_id=get_trace_id())


@router.post("/{taxonomy_id}/merge")
def merge_taxonomy(
    kb_id: UUID,
    taxonomy_id: UUID,
    body: MergeTaxonomyRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    source = _get_taxonomy_or_404(db, kb_id, taxonomy_id)
    target = _get_taxonomy_or_404(db, kb_id, body.target_taxonomy_id)
    try:
        result = merge_chapter_taxonomy(
            db,
            source,
            target,
            operator_id=operator_id,
            trace_id=get_trace_id(),
        )
    except MergeError as exc:
        return _merge_error_response(exc)
    return success(result, trace_id=get_trace_id())


@router.post("/{taxonomy_id}/deactivate")
def deactivate_taxonomy(
    kb_id: UUID,
    taxonomy_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    tax = _get_taxonomy_or_404(db, kb_id, taxonomy_id)
    try:
        tax = svc.deactivate_taxonomy(db, tax)
    except InvalidStateError as exc:
        return _invalid_state_response(exc)

    return success(
        {"taxonomy_id": str(tax.taxonomy_id), "status": tax.status.value},
        trace_id=get_trace_id(),
    )


@router.post("/{taxonomy_id}/archive")
def archive_taxonomy(
    kb_id: UUID,
    taxonomy_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    __: str = Depends(get_operator_id),
):
    tax = _get_taxonomy_or_404(db, kb_id, taxonomy_id)
    tax = svc.archive_taxonomy(db, tax)
    return success(
        {"taxonomy_id": str(tax.taxonomy_id), "status": tax.status.value},
        trace_id=get_trace_id(),
    )
