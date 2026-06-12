from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.document import Document


class ActualBidConfirmServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


@dataclass
class ActualBidConfirmResult:
    parse_task_id: UUID
    document_id: UUID
    bid_outline_id: UUID
    status: str
    structure_locked_at: datetime | None
    updated_outline_nodes: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: Any, *, field_name: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ActualBidConfirmServiceError(
            f"Invalid UUID for {field_name}",
            code="INVALID_INPUT",
            status_code=422,
        ) from exc


def apply_confirm(
    db: Session,
    task: ActualBidParseTask,
    payload: dict[str, Any],
    operator_id: str,
) -> ActualBidConfirmResult:
    _ = operator_id
    if task.status != ActualBidParseTaskStatus.ready:
        raise ActualBidConfirmServiceError(
            "Only ready tasks can be confirmed",
            code="INVALID_STATE",
            status_code=422,
        )
    if task.document_id is None:
        raise ActualBidConfirmServiceError(
            "Parse task document is missing",
            code="INVALID_STATE",
            status_code=422,
        )
    if task.bid_outline_id is None:
        raise ActualBidConfirmServiceError(
            "Parse task bid outline is missing",
            code="INVALID_STATE",
            status_code=422,
        )

    document = (
        db.query(Document)
        .filter(Document.kb_id == task.kb_id, Document.document_id == task.document_id)
        .one_or_none()
    )
    if document is None:
        raise ActualBidConfirmServiceError("Document not found", code="NOT_FOUND", status_code=404)

    bid_outline = (
        db.query(BidOutline)
        .filter(BidOutline.kb_id == task.kb_id, BidOutline.bid_outline_id == task.bid_outline_id)
        .one_or_none()
    )
    if bid_outline is None:
        raise ActualBidConfirmServiceError("Bid outline not found", code="NOT_FOUND", status_code=404)

    document_payload = payload.get("document")
    if not isinstance(document_payload, dict):
        raise ActualBidConfirmServiceError(
            "document must be an object",
            code="INVALID_INPUT",
            status_code=422,
        )
    if "bid_project_name" in document_payload:
        document.bid_project_name = document_payload.get("bid_project_name")
    if "bid_customer_name" in document_payload:
        document.bid_customer_name = document_payload.get("bid_customer_name")
    if "product_category_ids" in document_payload:
        product_category_ids = document_payload.get("product_category_ids")
        if product_category_ids is None:
            document.product_category_ids = []
        elif isinstance(product_category_ids, list):
            document.product_category_ids = list(product_category_ids)
        else:
            raise ActualBidConfirmServiceError(
                "document.product_category_ids must be a list",
                code="INVALID_INPUT",
                status_code=422,
            )
    document.confirmed_metadata = True

    outline_nodes_payload = payload.get("outline_nodes")
    if not isinstance(outline_nodes_payload, list):
        raise ActualBidConfirmServiceError(
            "outline_nodes must be a list",
            code="INVALID_INPUT",
            status_code=422,
        )

    outline_nodes = (
        db.query(BidOutlineNode)
        .filter(
            BidOutlineNode.kb_id == task.kb_id,
            BidOutlineNode.bid_outline_id == bid_outline.bid_outline_id,
        )
        .all()
    )
    node_by_id = {node.outline_node_id: node for node in outline_nodes}
    updated_outline_nodes = 0
    for item in outline_nodes_payload:
        if not isinstance(item, dict):
            raise ActualBidConfirmServiceError(
                "outline_nodes item must be an object",
                code="INVALID_INPUT",
                status_code=422,
            )
        outline_node_id = _as_uuid(item.get("outline_node_id"), field_name="outline_node_id")
        node = node_by_id.get(outline_node_id)
        if node is None:
            raise ActualBidConfirmServiceError(
                f"Outline node not found: {outline_node_id}",
                code="NOT_FOUND",
                status_code=404,
            )
        node.parent_id = (
            _as_uuid(item.get("parent_id"), field_name="parent_id") if item.get("parent_id") else None
        )
        node.title = str(item.get("title", "")).strip() or node.title
        node.level = int(item.get("level", node.level))
        node.sort_order = int(item.get("sort_order", node.sort_order))
        node.chapter_taxonomy_id = (
            _as_uuid(item.get("chapter_taxonomy_id"), field_name="chapter_taxonomy_id")
            if item.get("chapter_taxonomy_id")
            else None
        )
        node.product_category_ids = item.get("product_category_ids") or []
        node.needs_manual_review = bool(item.get("needs_manual_review", node.needs_manual_review))
        updated_outline_nodes += 1

    task.status = ActualBidParseTaskStatus.confirmed
    task.finished_at = _now()
    bid_outline.project_name = document.bid_project_name
    bid_outline.customer_name = document.bid_customer_name
    bid_outline.product_category_ids = document.product_category_ids or []

    db.commit()
    return ActualBidConfirmResult(
        parse_task_id=task.parse_task_id,
        document_id=document.document_id,
        bid_outline_id=bid_outline.bid_outline_id,
        status=task.status.value,
        structure_locked_at=bid_outline.structure_locked_at,
        updated_outline_nodes=updated_outline_nodes,
    )
