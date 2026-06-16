from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.services.content_blocks import blocks_v1, parse_content
from src.services.section_content_builder import build_section_content


class OutlineNotFoundError(Exception):
    pass


class OutlineNodeNotFoundError(Exception):
    pass


def _collect_subtree_ids(
    nodes_by_id: dict[UUID, BidOutlineNode],
    children_by_parent: dict[UUID | None, list[BidOutlineNode]],
    root_id: UUID,
) -> list[UUID]:
    ordered: list[UUID] = []

    def walk(node_id: UUID) -> None:
        ordered.append(node_id)
        for child in children_by_parent.get(node_id, []):
            walk(child.outline_node_id)

    walk(root_id)
    return ordered


def _serialize_section(node: BidOutlineNode, *, document_id: UUID, db: Session) -> dict[str, Any]:
    if node.source_node_id is None:
        content = blocks_v1([])
        return {
            "outline_node_id": str(node.outline_node_id),
            "title": node.title,
            "level": node.level,
            "sort_order": node.sort_order,
            "source_node_id": None,
            "content": content,
            "has_content": False,
            "empty_reason": "no_source_node",
        }

    content = build_section_content(
        db,
        document_id=document_id,
        heading_node_id=node.source_node_id,
    )
    parsed = parse_content(content)
    has_content = len(parsed.blocks) > 0
    return {
        "outline_node_id": str(node.outline_node_id),
        "title": node.title,
        "level": node.level,
        "sort_order": node.sort_order,
        "source_node_id": str(node.source_node_id),
        "content": content,
        "has_content": has_content,
        "empty_reason": None if has_content else "empty_body",
    }


def build_outline_subtree_content(
    db: Session,
    *,
    kb_id: UUID,
    bid_outline_id: UUID,
    outline_node_id: UUID,
) -> dict[str, Any]:
    outline = (
        db.query(BidOutline)
        .filter(BidOutline.kb_id == kb_id, BidOutline.bid_outline_id == bid_outline_id)
        .one_or_none()
    )
    if outline is None:
        raise OutlineNotFoundError

    nodes = (
        db.query(BidOutlineNode)
        .filter(
            BidOutlineNode.kb_id == kb_id,
            BidOutlineNode.bid_outline_id == bid_outline_id,
        )
        .order_by(
            BidOutlineNode.level.asc(),
            BidOutlineNode.sort_order.asc(),
            BidOutlineNode.created_at.asc(),
        )
        .all()
    )
    nodes_by_id = {node.outline_node_id: node for node in nodes}
    if outline_node_id not in nodes_by_id:
        raise OutlineNodeNotFoundError

    children_by_parent: dict[UUID | None, list[BidOutlineNode]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)
    for children in children_by_parent.values():
        children.sort(key=lambda item: (item.sort_order, item.created_at))

    subtree_ids = _collect_subtree_ids(nodes_by_id, children_by_parent, outline_node_id)
    root = nodes_by_id[outline_node_id]
    sections = [
        _serialize_section(nodes_by_id[node_id], document_id=outline.source_doc_id, db=db)
        for node_id in subtree_ids
    ]

    return {
        "outline_node_id": str(root.outline_node_id),
        "title": root.title,
        "bid_outline_id": str(outline.bid_outline_id),
        "source_doc_id": str(outline.source_doc_id),
        "sections": sections,
    }
