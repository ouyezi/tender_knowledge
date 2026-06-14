from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.content_blocks import blocks_v1


def _append_body_block(body_blocks: list[dict], node: DocumentTreeNode) -> None:
    if node.node_type == DocumentTreeNodeType.paragraph:
        text = (node.content_preview or "").strip()
        if text:
            body_blocks.append({"type": "paragraph", "text": text})
        return
    if node.node_type == DocumentTreeNodeType.table:
        text = (node.content_preview or "").strip()
        if text:
            body_blocks.append({"type": "table", "text": text})
        return
    if node.node_type == DocumentTreeNodeType.image:
        asset_id = (node.content_ref or "").strip() or None
        body_blocks.append(
            {
                "type": "image",
                "asset_id": asset_id,
                "fallback": None if asset_id else "[image]",
            }
        )


def _nested_zone_end(
    nodes: list[DocumentTreeNode],
    nested_idx: int,
    *,
    nested_level: int,
    heading_level: int,
) -> int:
    """Exclusive end index for a nested heading's direct content run."""
    zone_end = nested_idx + 1
    has_body = False
    while zone_end < len(nodes):
        inner = nodes[zone_end]
        if inner.node_type == DocumentTreeNodeType.heading:
            inner_level = inner.level or heading_level
            if inner_level <= nested_level:
                break
            zone_end = _nested_zone_end(
                nodes,
                zone_end,
                nested_level=inner_level,
                heading_level=heading_level,
            )
            continue
        if has_body:
            break
        has_body = True
        zone_end += 1
    return zone_end


def build_section_content(
    db: Session,
    *,
    document_id: UUID,
    heading_node_id: UUID,
) -> str:
    nodes = (
        db.query(DocumentTreeNode)
        .filter(DocumentTreeNode.document_id == document_id)
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    heading = next((n for n in nodes if n.node_id == heading_node_id), None)
    if heading is None or heading.node_type != DocumentTreeNodeType.heading:
        return blocks_v1([])

    start_idx = next(i for i, n in enumerate(nodes) if n.node_id == heading_node_id)
    heading_level = heading.level or 1
    body_blocks: list[dict] = []

    idx = start_idx + 1
    while idx < len(nodes):
        node = nodes[idx]
        if node.node_type == DocumentTreeNodeType.heading:
            node_level = node.level or heading_level
            if node_level <= heading_level:
                break
            idx = _nested_zone_end(
                nodes,
                idx,
                nested_level=node_level,
                heading_level=heading_level,
            )
            continue
        _append_body_block(body_blocks, node)
        idx += 1

    return blocks_v1(body_blocks)
