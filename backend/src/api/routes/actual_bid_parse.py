from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.document import Document
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.downstream_task_entry import DownstreamTaskEntry, DownstreamTaskType
from src.models.knowledge_base import KnowledgeBase
from src.services.actual_bid_parse_runner import (
    ActualBidParseServiceError,
    enqueue_actual_bid_parse,
    run_actual_bid_parse_in_new_session,
)
from src.api.deps import get_operator_id

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/actual-bid-parse",
    tags=["actual-bid-parse"],
)


class TriggerActualBidParseRequest(BaseModel):
    import_id: UUID
    force_reparse: bool = False


class PatchDocumentRequest(BaseModel):
    bid_project_name: str | None = None
    bid_customer_name: str | None = None
    product_category_ids: list[UUID] | None = None


def _serialize_document(db: Session, document: Document) -> dict:
    latest_task = (
        db.query(ActualBidParseTask)
        .filter(
            ActualBidParseTask.kb_id == document.kb_id,
            ActualBidParseTask.document_id == document.document_id,
        )
        .order_by(ActualBidParseTask.created_at.desc())
        .first()
    )
    bid_outline_id = None
    if latest_task and latest_task.bid_outline_id:
        bid_outline_id = str(latest_task.bid_outline_id)

    return {
        "document_id": str(document.document_id),
        "import_id": str(document.import_id),
        "source_type": document.source_type.value,
        "source_usage": document.source_usage.value,
        "product_category_ids": document.product_category_ids or [],
        "bid_project_name": document.bid_project_name,
        "bid_customer_name": document.bid_customer_name,
        "document_name": document.document_name,
        "parse_status": document.parse_status.value,
        "tree_version": document.tree_version,
        "bid_outline_id": bid_outline_id,
    }


def _serialize_tree_node(node: DocumentTreeNode) -> dict:
    return {
        "node_id": str(node.node_id),
        "parent_id": str(node.parent_id) if node.parent_id else None,
        "node_type": node.node_type.value,
        "title": node.title,
        "level": node.level,
        "sort_order": node.sort_order,
        "chapter_taxonomy_id": str(node.chapter_taxonomy_id) if node.chapter_taxonomy_id else None,
        "product_category_ids": node.product_category_ids or [],
        "is_outline_node": node.is_outline_node,
        "needs_manual_review": node.needs_manual_review,
        "content_preview": node.content_preview,
    }


@router.get("/tasks")
def list_parse_tasks(
    kb_id: UUID,
    import_id: UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    offset = max(page - 1, 0) * page_size
    q = db.query(ActualBidParseTask).filter(ActualBidParseTask.kb_id == kb_id)
    if import_id:
        q = q.filter(ActualBidParseTask.import_id == import_id)
    if status:
        q = q.filter(ActualBidParseTask.status == status)
    total = q.count()
    rows = (
        q.order_by(ActualBidParseTask.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [
                {
                    "parse_task_id": str(row.parse_task_id),
                    "import_id": str(row.import_id),
                    "document_id": str(row.document_id) if row.document_id else None,
                    "bid_outline_id": str(row.bid_outline_id) if row.bid_outline_id else None,
                    "task_phase": row.task_phase.value if row.task_phase else None,
                    "status": row.status.value,
                    "parse_strategy": row.parse_strategy.value if row.parse_strategy else None,
                    "error_message": row.error_message,
                    "retry_count": row.retry_count,
                    "llm_progress": row.llm_progress,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        trace_id=get_trace_id(),
    )


@router.post("/trigger", status_code=202)
def trigger_parse(
    kb_id: UUID,
    body: TriggerActualBidParseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    try:
        task = enqueue_actual_bid_parse(
            db,
            kb_id=kb_id,
            import_id=body.import_id,
            operator_id=operator_id,
            trace_id=get_trace_id(),
            force_reparse=body.force_reparse,
        )
    except ActualBidParseServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    background_tasks.add_task(run_actual_bid_parse_in_new_session)
    return success(
        {
            "parse_task_id": str(task.parse_task_id),
            "import_id": str(task.import_id),
            "document_id": str(task.document_id) if task.document_id else None,
            "status": task.status.value,
            "trace_id": str(task.trace_id) if task.trace_id else None,
        },
        trace_id=get_trace_id(),
    )


@router.get("/tasks/{parse_task_id}")
def get_parse_task(
    kb_id: UUID,
    parse_task_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    task = (
        db.query(ActualBidParseTask)
        .filter(
            ActualBidParseTask.kb_id == kb_id,
            ActualBidParseTask.parse_task_id == parse_task_id,
        )
        .one_or_none()
    )
    if task is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Parse task not found", trace_id=get_trace_id()),
        )

    suggestion = (
        db.query(DocumentParseSuggestion)
        .filter(DocumentParseSuggestion.parse_task_id == parse_task_id)
        .one_or_none()
    )
    downstream_entries = (
        db.query(DownstreamTaskEntry)
        .filter(
            DownstreamTaskEntry.kb_id == kb_id,
            DownstreamTaskEntry.import_id == task.import_id,
            DownstreamTaskEntry.task_type.in_(
                [
                    DownstreamTaskType.document_parse,
                    DownstreamTaskType.bid_outline_extract,
                    DownstreamTaskType.candidate_knowledge_generate,
                ]
            ),
        )
        .order_by(DownstreamTaskEntry.created_at.asc())
        .all()
    )

    suggestion_payload = suggestion.payload if suggestion else {}
    walk_result = suggestion_payload.get("walk_result") if isinstance(suggestion_payload, dict) else {}
    if not isinstance(walk_result, dict):
        walk_result = {}

    return success(
        {
            "parse_task_id": str(task.parse_task_id),
            "import_id": str(task.import_id),
            "document_id": str(task.document_id) if task.document_id else None,
            "bid_outline_id": str(task.bid_outline_id) if task.bid_outline_id else None,
            "task_phase": task.task_phase.value if task.task_phase else None,
            "status": task.status.value,
            "parse_strategy": task.parse_strategy.value if task.parse_strategy else None,
            "error_message": task.error_message,
            "retry_count": task.retry_count,
            "llm_progress": task.llm_progress,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "created_at": task.created_at.isoformat(),
            "suggestion": (
                {
                    "outline_extract_strategy": suggestion_payload.get("outline_extract_strategy"),
                    "node_count": walk_result.get("node_count"),
                    "candidate_count": suggestion_payload.get("candidate_count"),
                    "needs_manual_review": walk_result.get("needs_manual_review"),
                }
                if suggestion
                else None
            ),
            "downstream_entries": [
                {
                    "task_type": entry.task_type.value,
                    "status": entry.status.value,
                }
                for entry in downstream_entries
            ],
        },
        trace_id=get_trace_id(),
    )


@router.get("/documents/{document_id}")
def get_document(
    kb_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    document = (
        db.query(Document)
        .filter(Document.kb_id == kb_id, Document.document_id == document_id)
        .one_or_none()
    )
    if document is None:
        return JSONResponse(
            status_code=404,
            content=error("DOCUMENT_NOT_FOUND", "Document not found", trace_id=get_trace_id()),
        )
    return success(_serialize_document(db, document), trace_id=get_trace_id())


@router.patch("/documents/{document_id}")
def patch_document(
    kb_id: UUID,
    document_id: UUID,
    body: PatchDocumentRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
):
    document = (
        db.query(Document)
        .filter(Document.kb_id == kb_id, Document.document_id == document_id)
        .one_or_none()
    )
    if document is None:
        return JSONResponse(
            status_code=404,
            content=error("DOCUMENT_NOT_FOUND", "Document not found", trace_id=get_trace_id()),
        )

    if body.bid_project_name is not None:
        document.bid_project_name = body.bid_project_name
    if body.bid_customer_name is not None:
        document.bid_customer_name = body.bid_customer_name
    if body.product_category_ids is not None:
        document.product_category_ids = [str(item) for item in body.product_category_ids]
    db.commit()
    db.refresh(document)
    return success(_serialize_document(db, document), trace_id=get_trace_id())


@router.get("/documents/{document_id}/tree")
def get_document_tree(
    kb_id: UUID,
    document_id: UUID,
    tree_version: int | None = None,
    node_type: str | None = None,
    max_depth: int | None = None,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    document = (
        db.query(Document)
        .filter(Document.kb_id == kb_id, Document.document_id == document_id)
        .one_or_none()
    )
    if document is None:
        return JSONResponse(
            status_code=404,
            content=error("DOCUMENT_NOT_FOUND", "Document not found", trace_id=get_trace_id()),
        )

    resolved_tree_version = tree_version if tree_version is not None else document.tree_version
    q = db.query(DocumentTreeNode).filter(
        DocumentTreeNode.kb_id == kb_id,
        DocumentTreeNode.document_id == document_id,
        DocumentTreeNode.tree_version == resolved_tree_version,
    )
    if node_type:
        try:
            resolved_node_type = DocumentTreeNodeType(node_type)
        except ValueError:
            return JSONResponse(
                status_code=422,
                content=error("VALIDATION", "invalid node_type", trace_id=get_trace_id()),
            )
        q = q.filter(DocumentTreeNode.node_type == resolved_node_type)

    nodes = q.order_by(DocumentTreeNode.sort_order.asc()).all()
    if max_depth is not None and nodes:
        node_by_id = {node.node_id: node for node in nodes}
        depth_by_id: dict[UUID, int] = {}
        for node in nodes:
            depth = 0
            current = node
            while current.parent_id is not None and current.parent_id in node_by_id:
                depth += 1
                current = node_by_id[current.parent_id]
            depth_by_id[node.node_id] = depth
        nodes = [node for node in nodes if depth_by_id.get(node.node_id, 0) <= max_depth]

    return success(
        {
            "document_id": str(document_id),
            "tree_version": resolved_tree_version,
            "nodes": [_serialize_tree_node(node) for node in nodes],
        },
        trace_id=get_trace_id(),
    )
