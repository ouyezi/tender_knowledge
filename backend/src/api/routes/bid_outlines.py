from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.actual_bid_audit_log import ActualBidAuditLog
from src.models.bid_outline import BidOutline, BidOutlineStatus
from src.models.bid_outline_node import BidOutlineNode
from src.models.bid_outline_structure_diff import BidOutlineStructureDiff
from src.models.knowledge_base import KnowledgeBase
from src.services.bid_outline_diff_service import (
    BidOutlineDiffServiceError,
    apply_diff,
    reject_diff,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/bid-outlines",
    tags=["bid-outlines"],
)


class PatchOutlineNodeRequest(BaseModel):
    title: str | None = None
    parent_id: UUID | None = None
    level: int | None = Field(default=None, ge=1, le=9)
    sort_order: int | None = None
    chapter_taxonomy_id: UUID | None = None
    product_category_ids: list[UUID] | None = None
    needs_manual_review: bool | None = None


class BatchNodeOperation(BaseModel):
    op: str
    outline_node_id: UUID | None = None
    source_node_ids: list[UUID] = Field(default_factory=list)
    target_title: str | None = None
    parent_id: UUID | None = None
    ordered_node_ids: list[UUID] = Field(default_factory=list)


class BatchNodeOperationRequest(BaseModel):
    operations: list[BatchNodeOperation]


class ConfirmBidOutlineRequest(BaseModel):
    status: str


def _serialize_outline(outline: BidOutline) -> dict[str, object]:
    return {
        "bid_outline_id": str(outline.bid_outline_id),
        "source_doc_id": str(outline.source_doc_id),
        "import_id": str(outline.import_id),
        "outline_name": outline.outline_name,
        "outline_type": outline.outline_type.value,
        "status": outline.status.value,
        "extract_strategy": outline.extract_strategy.value,
        "project_name": outline.project_name,
        "customer_name": outline.customer_name,
        "product_category_ids": outline.product_category_ids or [],
        "structure_locked_at": (
            outline.structure_locked_at.isoformat() if outline.structure_locked_at else None
        ),
        "updated_at": outline.updated_at.isoformat(),
    }


def _serialize_outline_node(node: BidOutlineNode) -> dict[str, object]:
    return {
        "outline_node_id": str(node.outline_node_id),
        "parent_id": str(node.parent_id) if node.parent_id else None,
        "title": node.title,
        "level": node.level,
        "sort_order": node.sort_order,
        "chapter_taxonomy_id": str(node.chapter_taxonomy_id) if node.chapter_taxonomy_id else None,
        "source_node_id": str(node.source_node_id) if node.source_node_id else None,
        "product_category_ids": node.product_category_ids or [],
        "status": node.status.value,
        "needs_manual_review": node.needs_manual_review,
        "updated_at": node.updated_at.isoformat(),
    }


def _serialize_structure_diff(diff: BidOutlineStructureDiff) -> dict[str, object]:
    return {
        "diff_id": str(diff.diff_id),
        "bid_outline_id": str(diff.bid_outline_id),
        "parse_task_id": str(diff.parse_task_id),
        "status": diff.status.value,
        "diff_payload": diff.diff_payload or {},
        "resolved_by": diff.resolved_by,
        "resolved_at": diff.resolved_at.isoformat() if diff.resolved_at else None,
        "created_at": diff.created_at.isoformat(),
    }


def _append_actual_bid_audit_log(
    *,
    db: Session,
    kb_id: UUID,
    action: str,
    object_type: str,
    object_id: UUID,
    operator_id: str,
    detail: dict[str, object],
) -> ActualBidAuditLog:
    audit = ActualBidAuditLog(
        kb_id=kb_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        operator_id=operator_id,
        trace_id=get_trace_id(),
        detail=detail,
    )
    db.add(audit)
    return audit


def _get_outline_or_404(db: Session, kb_id: UUID, bid_outline_id: UUID) -> BidOutline | None:
    return (
        db.query(BidOutline)
        .filter(BidOutline.kb_id == kb_id, BidOutline.bid_outline_id == bid_outline_id)
        .one_or_none()
    )


def _recalculate_children_levels(
    nodes_by_id: dict[UUID, BidOutlineNode],
    parent_id: UUID | None,
    parent_level: int,
) -> None:
    children = [
        node
        for node in nodes_by_id.values()
        if node.parent_id == parent_id and node.outline_node_id in nodes_by_id
    ]
    for child in children:
        child.level = parent_level + 1
        _recalculate_children_levels(nodes_by_id, child.outline_node_id, child.level)


def _collect_subtree_ids(nodes_by_parent: dict[UUID | None, list[BidOutlineNode]], root_id: UUID) -> set[UUID]:
    stack = [root_id]
    visited: set[UUID] = set()
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        for child in nodes_by_parent.get(current, []):
            stack.append(child.outline_node_id)
    return visited


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


@router.get("/{bid_outline_id}")
def get_bid_outline_detail(
    kb_id: UUID,
    bid_outline_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    outline = _get_outline_or_404(db, kb_id, bid_outline_id)
    if outline is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )

    root_nodes = (
        db.query(BidOutlineNode)
        .filter(
            BidOutlineNode.kb_id == kb_id,
            BidOutlineNode.bid_outline_id == bid_outline_id,
            BidOutlineNode.parent_id.is_(None),
        )
        .order_by(BidOutlineNode.sort_order.asc(), BidOutlineNode.created_at.asc())
        .all()
    )
    return success(
        {
            **_serialize_outline(outline),
            "root_nodes": [_serialize_outline_node(node) for node in root_nodes],
        },
        trace_id=get_trace_id(),
    )


@router.get("/{bid_outline_id}/nodes")
def get_bid_outline_nodes(
    kb_id: UUID,
    bid_outline_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    outline = _get_outline_or_404(db, kb_id, bid_outline_id)
    if outline is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )

    nodes = (
        db.query(BidOutlineNode)
        .filter(
            BidOutlineNode.kb_id == kb_id,
            BidOutlineNode.bid_outline_id == bid_outline_id,
        )
        .order_by(BidOutlineNode.level.asc(), BidOutlineNode.sort_order.asc(), BidOutlineNode.created_at.asc())
        .all()
    )
    return success(
        {
            "bid_outline_id": str(bid_outline_id),
            "status": outline.status.value,
            "structure_locked_at": (
                outline.structure_locked_at.isoformat() if outline.structure_locked_at else None
            ),
            "nodes": [_serialize_outline_node(node) for node in nodes],
        },
        trace_id=get_trace_id(),
    )


@router.patch("/{bid_outline_id}/nodes/{outline_node_id}")
def patch_bid_outline_node(
    kb_id: UUID,
    bid_outline_id: UUID,
    outline_node_id: UUID,
    body: PatchOutlineNodeRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    outline = _get_outline_or_404(db, kb_id, bid_outline_id)
    if outline is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )

    node = (
        db.query(BidOutlineNode)
        .filter(
            BidOutlineNode.kb_id == kb_id,
            BidOutlineNode.bid_outline_id == bid_outline_id,
            BidOutlineNode.outline_node_id == outline_node_id,
        )
        .one_or_none()
    )
    if node is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NODE_NOT_FOUND", "Outline node not found", trace_id=get_trace_id()),
        )

    old_values = _serialize_outline_node(node)
    payload = body.model_dump(exclude_unset=True)
    if "parent_id" in payload:
        parent_id = payload.get("parent_id")
        if parent_id == outline_node_id:
            return JSONResponse(
                status_code=400,
                content=error(
                    "INVALID_TREE_OPERATION",
                    "Node parent cannot be itself",
                    trace_id=get_trace_id(),
                ),
            )
        if parent_id is not None:
            parent = (
                db.query(BidOutlineNode)
                .filter(
                    BidOutlineNode.kb_id == kb_id,
                    BidOutlineNode.bid_outline_id == bid_outline_id,
                    BidOutlineNode.outline_node_id == parent_id,
                )
                .one_or_none()
            )
            if parent is None:
                return JSONResponse(
                    status_code=400,
                    content=error(
                        "INVALID_TREE_OPERATION",
                        "Parent node not found in outline",
                        trace_id=get_trace_id(),
                    ),
                )
            node.level = parent.level + 1
        else:
            node.level = 1
        node.parent_id = parent_id

    if "title" in payload and payload["title"] is not None:
        title = str(payload["title"]).strip()
        if title:
            node.title = title
    if "level" in payload and payload["level"] is not None:
        node.level = payload["level"]
    if "sort_order" in payload and payload["sort_order"] is not None:
        node.sort_order = payload["sort_order"]
    if "chapter_taxonomy_id" in payload:
        node.chapter_taxonomy_id = payload["chapter_taxonomy_id"]
    if "product_category_ids" in payload and payload["product_category_ids"] is not None:
        node.product_category_ids = [str(item) for item in payload["product_category_ids"]]
    if "needs_manual_review" in payload and payload["needs_manual_review"] is not None:
        node.needs_manual_review = payload["needs_manual_review"]

    outline.updated_at = datetime.now(timezone.utc)
    db.flush()
    audit = _append_actual_bid_audit_log(
        db=db,
        kb_id=kb_id,
        action="outline_node_patch",
        object_type="bid_outline_node",
        object_id=node.outline_node_id,
        operator_id=operator_id,
        detail={
            "bid_outline_id": str(bid_outline_id),
            "before": old_values,
            "after": _serialize_outline_node(node),
        },
    )
    db.commit()
    db.refresh(node)
    db.refresh(audit)
    return success(
        {"node": _serialize_outline_node(node), "audit_id": str(audit.audit_id)},
        trace_id=get_trace_id(),
    )


@router.post("/{bid_outline_id}/confirm")
def confirm_bid_outline(
    kb_id: UUID,
    bid_outline_id: UUID,
    body: ConfirmBidOutlineRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    if body.status != BidOutlineStatus.confirmed.value:
        return JSONResponse(
            status_code=400,
            content=error(
                "INVALID_OUTLINE_STATUS",
                "Only confirmed status is supported",
                trace_id=get_trace_id(),
            ),
        )

    outline = _get_outline_or_404(db, kb_id, bid_outline_id)
    if outline is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )

    now = datetime.now(timezone.utc)
    outline.status = BidOutlineStatus.confirmed
    outline.structure_locked_at = now
    outline.structure_locked_by = operator_id
    outline.updated_at = now

    audit = _append_actual_bid_audit_log(
        db=db,
        kb_id=kb_id,
        action="outline_confirmed",
        object_type="bid_outline",
        object_id=bid_outline_id,
        operator_id=operator_id,
        detail={
            "bid_outline_id": str(bid_outline_id),
            "status": BidOutlineStatus.confirmed.value,
            "structure_locked_at": now.isoformat(),
        },
    )
    db.commit()
    db.refresh(outline)
    db.refresh(audit)
    return success(
        {**_serialize_outline(outline), "audit_id": str(audit.audit_id)},
        trace_id=get_trace_id(),
    )


@router.post("/{bid_outline_id}/nodes/batch")
def batch_operate_bid_outline_nodes(
    kb_id: UUID,
    bid_outline_id: UUID,
    body: BatchNodeOperationRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    outline = _get_outline_or_404(db, kb_id, bid_outline_id)
    if outline is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )
    if not body.operations:
        return JSONResponse(
            status_code=400,
            content=error(
                "INVALID_TREE_OPERATION",
                "operations cannot be empty",
                trace_id=get_trace_id(),
            ),
        )

    nodes = (
        db.query(BidOutlineNode)
        .filter(
            BidOutlineNode.kb_id == kb_id,
            BidOutlineNode.bid_outline_id == bid_outline_id,
        )
        .all()
    )
    nodes_by_id: dict[UUID, BidOutlineNode] = {node.outline_node_id: node for node in nodes}
    operation_summaries: list[dict[str, object]] = []

    for operation in body.operations:
        if operation.op == "delete":
            if operation.outline_node_id is None:
                return JSONResponse(
                    status_code=400,
                    content=error(
                        "INVALID_TREE_OPERATION",
                        "delete requires outline_node_id",
                        trace_id=get_trace_id(),
                    ),
                )
            target = nodes_by_id.get(operation.outline_node_id)
            if target is None:
                return JSONResponse(
                    status_code=404,
                    content=error(
                        "OUTLINE_NODE_NOT_FOUND",
                        "Outline node not found",
                        trace_id=get_trace_id(),
                    ),
                )
            nodes_by_parent: dict[UUID | None, list[BidOutlineNode]] = {}
            for item in nodes_by_id.values():
                nodes_by_parent.setdefault(item.parent_id, []).append(item)
            to_delete = _collect_subtree_ids(nodes_by_parent, target.outline_node_id)
            for node_id in to_delete:
                node_obj = nodes_by_id.pop(node_id, None)
                if node_obj is not None:
                    db.delete(node_obj)
            operation_summaries.append(
                {
                    "op": "delete",
                    "outline_node_id": str(operation.outline_node_id),
                    "deleted_count": len(to_delete),
                }
            )
            continue

        if operation.op == "merge":
            if len(operation.source_node_ids) < 2:
                return JSONResponse(
                    status_code=400,
                    content=error(
                        "INVALID_TREE_OPERATION",
                        "merge requires at least two source_node_ids",
                        trace_id=get_trace_id(),
                    ),
                )
            missing = [str(node_id) for node_id in operation.source_node_ids if node_id not in nodes_by_id]
            if missing:
                return JSONResponse(
                    status_code=404,
                    content=error(
                        "OUTLINE_NODE_NOT_FOUND",
                        f"Outline node not found: {', '.join(missing)}",
                        trace_id=get_trace_id(),
                    ),
                )

            primary = nodes_by_id[operation.source_node_ids[0]]
            primary_parent_id = primary.parent_id
            primary_level = primary.level
            primary_sort = primary.sort_order
            for source_id in operation.source_node_ids[1:]:
                source = nodes_by_id[source_id]
                if source.parent_id != primary_parent_id or source.level != primary_level:
                    return JSONResponse(
                        status_code=400,
                        content=error(
                            "INVALID_TREE_OPERATION",
                            "merge nodes must have same parent and level",
                            trace_id=get_trace_id(),
                        ),
                    )
                children = [node for node in nodes_by_id.values() if node.parent_id == source.outline_node_id]
                for child in children:
                    child.parent_id = primary.outline_node_id
                db.delete(source)
                nodes_by_id.pop(source.outline_node_id, None)

            if operation.target_title and operation.target_title.strip():
                primary.title = operation.target_title.strip()
            primary.sort_order = primary_sort
            operation_summaries.append(
                {
                    "op": "merge",
                    "primary_node_id": str(primary.outline_node_id),
                    "merged_node_ids": [str(item) for item in operation.source_node_ids[1:]],
                }
            )
            continue

        if operation.op == "reorder":
            ordered_ids = operation.ordered_node_ids
            if not ordered_ids:
                return JSONResponse(
                    status_code=400,
                    content=error(
                        "INVALID_TREE_OPERATION",
                        "reorder requires ordered_node_ids",
                        trace_id=get_trace_id(),
                    ),
                )
            missing = [str(node_id) for node_id in ordered_ids if node_id not in nodes_by_id]
            if missing:
                return JSONResponse(
                    status_code=404,
                    content=error(
                        "OUTLINE_NODE_NOT_FOUND",
                        f"Outline node not found: {', '.join(missing)}",
                        trace_id=get_trace_id(),
                    ),
                )

            parent_level = 0
            if operation.parent_id is not None:
                parent = nodes_by_id.get(operation.parent_id)
                if parent is None:
                    return JSONResponse(
                        status_code=400,
                        content=error(
                            "INVALID_TREE_OPERATION",
                            "reorder parent node not found",
                            trace_id=get_trace_id(),
                        ),
                    )
                parent_level = parent.level

            for index, node_id in enumerate(ordered_ids):
                node = nodes_by_id[node_id]
                node.parent_id = operation.parent_id
                node.level = parent_level + 1
                node.sort_order = index
                _recalculate_children_levels(nodes_by_id, node.outline_node_id, node.level)

            operation_summaries.append(
                {
                    "op": "reorder",
                    "parent_id": str(operation.parent_id) if operation.parent_id else None,
                    "ordered_node_ids": [str(item) for item in ordered_ids],
                }
            )
            continue

        return JSONResponse(
            status_code=400,
            content=error(
                "INVALID_TREE_OPERATION",
                f"unsupported operation: {operation.op}",
                trace_id=get_trace_id(),
            ),
        )

    outline.updated_at = datetime.now(timezone.utc)
    db.flush()
    audit = _append_actual_bid_audit_log(
        db=db,
        kb_id=kb_id,
        action="outline_nodes_batch",
        object_type="bid_outline",
        object_id=bid_outline_id,
        operator_id=operator_id,
        detail={"operations": operation_summaries},
    )
    db.commit()
    db.refresh(audit)

    refreshed_nodes = (
        db.query(BidOutlineNode)
        .filter(
            BidOutlineNode.kb_id == kb_id,
            BidOutlineNode.bid_outline_id == bid_outline_id,
        )
        .order_by(BidOutlineNode.level.asc(), BidOutlineNode.sort_order.asc(), BidOutlineNode.created_at.asc())
        .all()
    )
    return success(
        {
            "bid_outline_id": str(bid_outline_id),
            "nodes": [_serialize_outline_node(node) for node in refreshed_nodes],
            "audit_id": str(audit.audit_id),
        },
        trace_id=get_trace_id(),
    )


@router.get("/{bid_outline_id}/diffs")
def list_bid_outline_diffs(
    kb_id: UUID,
    bid_outline_id: UUID,
    status: str | None = None,
    parse_task_id: UUID | None = None,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    outline = _get_outline_or_404(db, kb_id, bid_outline_id)
    if outline is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )
    query = db.query(BidOutlineStructureDiff).filter(
        BidOutlineStructureDiff.kb_id == kb_id,
        BidOutlineStructureDiff.bid_outline_id == bid_outline_id,
    )
    if status:
        query = query.filter(BidOutlineStructureDiff.status == status)
    if parse_task_id:
        query = query.filter(BidOutlineStructureDiff.parse_task_id == parse_task_id)
    diffs = query.order_by(BidOutlineStructureDiff.created_at.desc()).all()
    return success(
        {
            "bid_outline_id": str(bid_outline_id),
            "items": [_serialize_structure_diff(item) for item in diffs],
        },
        trace_id=get_trace_id(),
    )


@router.post("/{bid_outline_id}/diffs/{diff_id}/apply")
def apply_bid_outline_diff(
    kb_id: UUID,
    bid_outline_id: UUID,
    diff_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    outline = _get_outline_or_404(db, kb_id, bid_outline_id)
    if outline is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )
    diff = (
        db.query(BidOutlineStructureDiff)
        .filter(
            BidOutlineStructureDiff.kb_id == kb_id,
            BidOutlineStructureDiff.bid_outline_id == bid_outline_id,
            BidOutlineStructureDiff.diff_id == diff_id,
        )
        .one_or_none()
    )
    if diff is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Structure diff not found", trace_id=get_trace_id()),
        )
    try:
        refreshed_nodes = apply_diff(db, outline=outline, diff=diff, operator_id=operator_id)
    except BidOutlineDiffServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    audit = _append_actual_bid_audit_log(
        db=db,
        kb_id=kb_id,
        action="outline_diff_apply",
        object_type="bid_outline_structure_diff",
        object_id=diff.diff_id,
        operator_id=operator_id,
        detail={"bid_outline_id": str(bid_outline_id), "parse_task_id": str(diff.parse_task_id)},
    )
    db.commit()
    db.refresh(audit)
    return success(
        {
            "bid_outline_id": str(bid_outline_id),
            "structure_diff": _serialize_structure_diff(diff),
            "nodes": [_serialize_outline_node(node) for node in refreshed_nodes],
            "audit_id": str(audit.audit_id),
        },
        trace_id=get_trace_id(),
    )


@router.post("/{bid_outline_id}/diffs/{diff_id}/reject")
def reject_bid_outline_diff(
    kb_id: UUID,
    bid_outline_id: UUID,
    diff_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    outline = _get_outline_or_404(db, kb_id, bid_outline_id)
    if outline is None:
        return JSONResponse(
            status_code=404,
            content=error("OUTLINE_NOT_FOUND", "Bid outline not found", trace_id=get_trace_id()),
        )
    diff = (
        db.query(BidOutlineStructureDiff)
        .filter(
            BidOutlineStructureDiff.kb_id == kb_id,
            BidOutlineStructureDiff.bid_outline_id == bid_outline_id,
            BidOutlineStructureDiff.diff_id == diff_id,
        )
        .one_or_none()
    )
    if diff is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Structure diff not found", trace_id=get_trace_id()),
        )
    try:
        reject_diff(db, diff=diff, operator_id=operator_id)
    except BidOutlineDiffServiceError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content=error(exc.code, str(exc), trace_id=get_trace_id()),
        )
    audit = _append_actual_bid_audit_log(
        db=db,
        kb_id=kb_id,
        action="outline_diff_reject",
        object_type="bid_outline_structure_diff",
        object_id=diff.diff_id,
        operator_id=operator_id,
        detail={"bid_outline_id": str(bid_outline_id), "parse_task_id": str(diff.parse_task_id)},
    )
    db.commit()
    db.refresh(audit)
    return success(
        {
            "bid_outline_id": str(bid_outline_id),
            "structure_diff": _serialize_structure_diff(diff),
            "audit_id": str(audit.audit_id),
        },
        trace_id=get_trace_id(),
    )
