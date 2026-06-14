from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.services.candidate_adapter import CandidateNotEditableError, CandidateNotFoundError
from src.services.candidate_edit_service import (
    InvalidProductCategoryError,
    InvalidTaxonomyError,
    edit_candidate,
)
from src.services.candidate_publish_service import PublishConflictError, publish
from src.services.candidate_publish_validator import PublishValidationError
from src.services.candidate_merge_service import (
    MergeInvalidTargetError,
    MergeSourceNotPendingError,
    SplitNotSupportedError,
    merge_candidates,
    split_candidate,
)
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.candidate_knowledge_stub import CandidateKnowledgeStub
from src.models.document import Document
from src.models.document_tree_node import DocumentTreeNode
from src.models.file_import import FileImport
from src.models.knowledge_base import KnowledgeBase
from src.models.template import Template
from src.models.template_chapter import TemplateChapter

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/candidates",
    tags=["candidates"],
)


class CandidatePatchRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    suggested_knowledge_type: str | None = None
    suggested_chapter_taxonomy_id: UUID | None = None
    suggested_product_category_ids: list[UUID] | None = None
    candidate_type: str | None = None


class ConfirmRequest(BaseModel):
    confirm_as: str
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    product_category_ids: list[UUID] | None = None
    chapter_taxonomy_id: UUID | None = None
    knowledge_type: str | None = None
    wiki_type: str | None = None
    asset_type: str | None = None
    searchable: bool | None = True
    usage_hint: str | None = None
    review_comment: str | None = None
    template_id: UUID | None = None
    parent_chapter_id: UUID | None = None
    category_code: str | None = None
    parent_category_id: UUID | None = None
    storage_path: str | None = None


class MergeRequest(BaseModel):
    target_candidate_id: str
    source_candidate_ids: list[str]
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    review_comment: str | None = None


class SplitItem(BaseModel):
    title: str
    summary: str | None = None
    content: str | None = None
    candidate_type: str
    suggested_knowledge_type: str | None = None
    suggested_chapter_taxonomy_id: UUID | None = None
    suggested_product_category_ids: list[UUID] | None = None


class SplitRequest(BaseModel):
    splits: list[SplitItem]
    review_comment: str | None = None


def _status_to_stub_status(status: str | None) -> str | None:
    if status == "pending":
        return "pending_confirm"
    return status


def _format_dt(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _doc_candidate_id(candidate_id: UUID) -> str:
    return f"doc_{candidate_id}"


def _tpl_candidate_id(stub_id: UUID) -> str:
    return f"tpl_{stub_id}"


def _candidate_not_found_response() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error("CANDIDATE_NOT_FOUND", "Candidate not found", trace_id=get_trace_id()),
    )


def _json_uuid_array_contains(column, category_id: UUID):
    value = str(category_id)
    return cast(column, String).contains(f'"{value}"')


@router.get("")
def list_candidates(
    kb_id: UUID,
    status: str = "pending",
    import_id: UUID | None = None,
    source_doc_id: UUID | None = None,
    candidate_type: str | None = None,
    source_channel: str = "all",
    chapter_taxonomy_id: UUID | None = None,
    product_category_id: UUID | None = None,
    confidence_min: float | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    include_document = source_channel in {"all", "document"}
    include_template = source_channel in {"all", "template"}
    rows: list[dict] = []

    if include_document:
        doc_q = (
            db.query(CandidateKnowledge, FileImport, Document, DocumentTreeNode)
            .join(FileImport, FileImport.import_id == CandidateKnowledge.import_id)
            .join(Document, Document.document_id == CandidateKnowledge.source_doc_id)
            .outerjoin(DocumentTreeNode, DocumentTreeNode.node_id == CandidateKnowledge.source_node_id)
            .filter(CandidateKnowledge.kb_id == kb_id)
            .filter(CandidateKnowledge.status == status)
        )
        if import_id:
            doc_q = doc_q.filter(CandidateKnowledge.import_id == import_id)
        if source_doc_id:
            doc_q = doc_q.filter(CandidateKnowledge.source_doc_id == source_doc_id)
        if candidate_type:
            doc_q = doc_q.filter(CandidateKnowledge.candidate_type == candidate_type)
        if chapter_taxonomy_id:
            doc_q = doc_q.filter(
                CandidateKnowledge.suggested_chapter_taxonomy_id == chapter_taxonomy_id
            )
        if product_category_id:
            doc_q = doc_q.filter(
                _json_uuid_array_contains(
                    CandidateKnowledge.suggested_product_category_ids,
                    product_category_id,
                )
            )
        if confidence_min is not None:
            doc_q = doc_q.filter(CandidateKnowledge.confidence_score >= confidence_min)

        for candidate, file_import, document, node in doc_q.all():
            rows.append(
                {
                    "candidate_id": _doc_candidate_id(candidate.candidate_id),
                    "source_channel": "document",
                    "import_id": str(candidate.import_id),
                    "source_doc_id": str(candidate.source_doc_id),
                    "source_node_id": str(candidate.source_node_id),
                    "candidate_type": candidate.candidate_type.value,
                    "title": candidate.title,
                    "summary": candidate.summary,
                    "suggested_knowledge_type": candidate.suggested_knowledge_type,
                    "suggested_chapter_taxonomy_id": (
                        str(candidate.suggested_chapter_taxonomy_id)
                        if candidate.suggested_chapter_taxonomy_id
                        else None
                    ),
                    "suggested_product_category_ids": candidate.suggested_product_category_ids,
                    "confidence_score": candidate.confidence_score,
                    "status": "pending" if candidate.status.value == "pending" else candidate.status.value,
                    "source_trace": {
                        "file_name": file_import.file_name,
                        "document_name": document.document_name,
                        "node_title": node.title if node else None,
                    },
                    "created_at": _format_dt(candidate.created_at),
                }
            )

    if include_template:
        stub_status = _status_to_stub_status(status)
        tpl_q = (
            db.query(CandidateKnowledgeStub, FileImport, Template, TemplateChapter)
            .join(FileImport, FileImport.import_id == CandidateKnowledgeStub.import_id)
            .join(Template, Template.template_id == CandidateKnowledgeStub.template_id)
            .outerjoin(
                TemplateChapter,
                TemplateChapter.template_chapter_id == CandidateKnowledgeStub.template_chapter_id,
            )
            .filter(CandidateKnowledgeStub.kb_id == kb_id)
        )
        if stub_status:
            tpl_q = tpl_q.filter(CandidateKnowledgeStub.status == stub_status)
        if import_id:
            tpl_q = tpl_q.filter(CandidateKnowledgeStub.import_id == import_id)
        if candidate_type:
            tpl_q = tpl_q.filter(CandidateKnowledgeStub.candidate_type == candidate_type)
        if source_doc_id:
            tpl_q = tpl_q.filter(CandidateKnowledgeStub.stub_id.is_(None))
        if chapter_taxonomy_id:
            tpl_q = tpl_q.filter(CandidateKnowledgeStub.chapter_taxonomy_id == chapter_taxonomy_id)
        if product_category_id:
            tpl_q = tpl_q.filter(
                _json_uuid_array_contains(
                    CandidateKnowledgeStub.product_category_ids,
                    product_category_id,
                )
            )
        if confidence_min is not None:
            tpl_q = tpl_q.filter(
                CandidateKnowledgeStub.classification_confidence >= confidence_min
            )

        for stub, file_import, template, chapter in tpl_q.all():
            rows.append(
                {
                    "candidate_id": _tpl_candidate_id(stub.stub_id),
                    "source_channel": "template",
                    "import_id": str(stub.import_id),
                    "source_doc_id": None,
                    "source_node_id": None,
                    "candidate_type": stub.candidate_type.value,
                    "title": stub.title,
                    "summary": stub.summary,
                    "suggested_knowledge_type": stub.suggested_knowledge_type,
                    "suggested_chapter_taxonomy_id": (
                        str(stub.chapter_taxonomy_id) if stub.chapter_taxonomy_id else None
                    ),
                    "suggested_product_category_ids": stub.product_category_ids,
                    "confidence_score": stub.classification_confidence,
                    "status": "pending" if stub.status.value == "pending_confirm" else stub.status.value,
                    "source_trace": {
                        "file_name": file_import.file_name,
                        "template_name": template.template_name,
                        "chapter_title": chapter.title if chapter else None,
                    },
                    "created_at": _format_dt(stub.created_at),
                }
            )

    rows.sort(key=lambda item: item["created_at"] or "", reverse=True)
    total = len(rows)
    offset = max(page - 1, 0) * page_size
    paged_rows = rows[offset : offset + page_size]
    return success(
        {"items": paged_rows, "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )


@router.get("/{candidate_id}")
def get_candidate_detail(
    kb_id: UUID,
    candidate_id: str,
    source_channel: str | None = None,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    if candidate_id.startswith("doc_"):
        source_channel = "document"
        raw_id = candidate_id.removeprefix("doc_")
    elif candidate_id.startswith("tpl_"):
        source_channel = "template"
        raw_id = candidate_id.removeprefix("tpl_")
    else:
        raw_id = candidate_id

    try:
        target_id = UUID(raw_id)
    except ValueError:
        return _candidate_not_found_response()

    if source_channel == "document":
        row = (
            db.query(CandidateKnowledge, FileImport, Document, DocumentTreeNode)
            .join(FileImport, FileImport.import_id == CandidateKnowledge.import_id)
            .join(Document, Document.document_id == CandidateKnowledge.source_doc_id)
            .outerjoin(DocumentTreeNode, DocumentTreeNode.node_id == CandidateKnowledge.source_node_id)
            .filter(CandidateKnowledge.kb_id == kb_id)
            .filter(CandidateKnowledge.candidate_id == target_id)
            .first()
        )
        if row is None:
            return _candidate_not_found_response()
        candidate, file_import, document, node = row
        return success(
            {
                "candidate_id": _doc_candidate_id(candidate.candidate_id),
                "source_channel": "document",
                "title": candidate.title,
                "content": candidate.content,
                "summary": candidate.summary,
                "status": "pending" if candidate.status.value == "pending" else candidate.status.value,
                "source_trace": {
                    "import_id": str(candidate.import_id),
                    "source_doc_id": str(candidate.source_doc_id),
                    "source_node_id": str(candidate.source_node_id),
                    "parse_task_id": str(candidate.parse_task_id) if candidate.parse_task_id else None,
                    "file_name": file_import.file_name,
                    "document_name": document.document_name,
                    "node_title": node.title if node else None,
                },
            },
            trace_id=get_trace_id(),
        )

    if source_channel == "template":
        row = (
            db.query(CandidateKnowledgeStub, FileImport, Template, TemplateChapter)
            .join(FileImport, FileImport.import_id == CandidateKnowledgeStub.import_id)
            .join(Template, Template.template_id == CandidateKnowledgeStub.template_id)
            .outerjoin(
                TemplateChapter,
                TemplateChapter.template_chapter_id == CandidateKnowledgeStub.template_chapter_id,
            )
            .filter(CandidateKnowledgeStub.kb_id == kb_id)
            .filter(CandidateKnowledgeStub.stub_id == target_id)
            .first()
        )
        if row is None:
            return _candidate_not_found_response()
        stub, file_import, template, chapter = row
        return success(
            {
                "candidate_id": _tpl_candidate_id(stub.stub_id),
                "source_channel": "template",
                "title": stub.title,
                "content": stub.content_preview,
                "summary": stub.summary,
                "status": "pending" if stub.status.value == "pending_confirm" else stub.status.value,
                "source_trace": {
                    "import_id": str(stub.import_id),
                    "template_id": str(stub.template_id),
                    "template_chapter_id": (
                        str(stub.template_chapter_id) if stub.template_chapter_id else None
                    ),
                    "material_id": str(stub.material_id) if stub.material_id else None,
                    "file_name": file_import.file_name,
                    "template_name": template.template_name,
                    "chapter_title": chapter.title if chapter else None,
                },
            },
            trace_id=get_trace_id(),
        )

    return _candidate_not_found_response()


@router.patch("/{candidate_id}")
def patch_candidate(
    kb_id: UUID,
    candidate_id: str,
    body: CandidatePatchRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    trace_id = get_trace_id() or UUID(int=0)
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return JSONResponse(
            status_code=422,
            content=error("VALIDATION_ERROR", "No fields to update", trace_id=trace_id),
        )

    try:
        result = edit_candidate(
            db,
            kb_id=kb_id,
            candidate_id=candidate_id,
            payload=payload,
            operator_id=operator_id,
            trace_id=trace_id,
        )
    except CandidateNotFoundError:
        return _candidate_not_found_response()
    except CandidateNotEditableError as exc:
        return JSONResponse(
            status_code=409,
            content=error(
                "CANDIDATE_NOT_EDITABLE",
                f"Candidate not editable in status={exc.status}",
                trace_id=trace_id,
            ),
        )
    except InvalidTaxonomyError:
        return JSONResponse(
            status_code=422,
            content=error(
                "INVALID_TAXONOMY",
                "Chapter taxonomy not found or inactive",
                trace_id=trace_id,
            ),
        )
    except InvalidProductCategoryError:
        return JSONResponse(
            status_code=422,
            content=error(
                "INVALID_PRODUCT_CATEGORY",
                "Product category not found or inactive",
                trace_id=trace_id,
            ),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content=error("VALIDATION_ERROR", str(exc), trace_id=trace_id),
        )

    return success(result, trace_id=trace_id)


def _publish_error_response(exc: Exception, trace_id: UUID) -> JSONResponse:
    if isinstance(exc, CandidateNotFoundError):
        return _candidate_not_found_response()
    if isinstance(exc, PublishConflictError):
        return JSONResponse(
            status_code=409,
            content=error("PUBLISH_CONFLICT", str(exc), trace_id=trace_id),
        )
    if isinstance(exc, PublishValidationError):
        return JSONResponse(
            status_code=422,
            content=error(exc.code, str(exc), trace_id=trace_id),
        )
    return JSONResponse(
        status_code=422,
        content=error("PUBLISH_VALIDATION_FAILED", str(exc), trace_id=trace_id),
    )


@router.post("/merge")
def merge_candidate(
    kb_id: UUID,
    body: MergeRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    trace_id = get_trace_id() or UUID(int=0)
    try:
        result = merge_candidates(
            db,
            kb_id=kb_id,
            target_candidate_id=body.target_candidate_id,
            source_candidate_ids=body.source_candidate_ids,
            payload=body.model_dump(exclude_unset=True),
            operator_id=operator_id,
            trace_id=trace_id,
        )
    except CandidateNotFoundError:
        return _candidate_not_found_response()
    except MergeInvalidTargetError:
        return JSONResponse(
            status_code=409,
            content=error("MERGE_INVALID_TARGET", "Invalid merge target", trace_id=trace_id),
        )
    except MergeSourceNotPendingError as exc:
        return JSONResponse(
            status_code=409,
            content=error(
                "MERGE_SOURCE_NOT_PENDING",
                f"Merge source not pending: {exc.candidate_id} status={exc.status}",
                trace_id=trace_id,
            ),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content=error("VALIDATION_ERROR", str(exc), trace_id=trace_id),
        )
    return success(result, trace_id=trace_id)


@router.post("/{candidate_id}/split")
def split_candidate_route(
    kb_id: UUID,
    candidate_id: str,
    body: SplitRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    trace_id = get_trace_id() or UUID(int=0)
    try:
        result = split_candidate(
            db,
            kb_id=kb_id,
            candidate_id=candidate_id,
            splits=[item.model_dump(exclude_unset=True) for item in body.splits],
            review_comment=body.review_comment,
            operator_id=operator_id,
            trace_id=trace_id,
        )
    except CandidateNotFoundError:
        return _candidate_not_found_response()
    except SplitNotSupportedError as exc:
        return JSONResponse(
            status_code=422,
            content=error("SPLIT_UNSUPPORTED_CHANNEL", str(exc), trace_id=trace_id),
        )
    except CandidateNotEditableError as exc:
        return JSONResponse(
            status_code=409,
            content=error(
                "CANDIDATE_NOT_EDITABLE",
                f"Candidate not editable in status={exc.status}",
                trace_id=trace_id,
            ),
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content=error("VALIDATION_ERROR", str(exc), trace_id=trace_id),
        )
    return success(result, trace_id=trace_id)


@router.post("/{candidate_id}/confirm")
def confirm_candidate(
    kb_id: UUID,
    candidate_id: str,
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    trace_id = get_trace_id() or UUID(int=0)
    try:
        result = publish(
            db,
            kb_id=kb_id,
            candidate_id=candidate_id,
            payload=body.model_dump(exclude_unset=True),
            operator_id=operator_id,
            trace_id=trace_id,
        )
    except Exception as exc:
        return _publish_error_response(exc, trace_id)
    return success(result, trace_id=trace_id)


@router.post("/{candidate_id}/retry-publish")
def retry_publish_candidate(
    kb_id: UUID,
    candidate_id: str,
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    trace_id = get_trace_id() or UUID(int=0)
    try:
        result = publish(
            db,
            kb_id=kb_id,
            candidate_id=candidate_id,
            payload=body.model_dump(exclude_unset=True),
            operator_id=operator_id,
            trace_id=trace_id,
        )
    except Exception as exc:
        return _publish_error_response(exc, trace_id)
    return success(result, trace_id=trace_id)
