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


def _children_by_parent(nodes: list[DocumentTreeNode]) -> dict[UUID | None, list[DocumentTreeNode]]:
    by_parent: dict[UUID | None, list[DocumentTreeNode]] = {}
    for node in nodes:
        by_parent.setdefault(node.parent_id, []).append(node)
    for children in by_parent.values():
        children.sort(key=lambda item: item.sort_order)
    return by_parent


def _collect_body_blocks_from_parent_tree(
    by_parent: dict[UUID | None, list[DocumentTreeNode]],
    heading_node_id: UUID,
) -> list[dict]:
    body_blocks: list[dict] = []

    def walk(parent_id: UUID) -> None:
        for child in by_parent.get(parent_id, []):
            if child.node_type == DocumentTreeNodeType.heading:
                walk(child.node_id)
                continue
            _append_body_block(body_blocks, child)

    walk(heading_node_id)
    return body_blocks


def _collect_body_blocks_linear(
    nodes: list[DocumentTreeNode],
    *,
    heading_node_id: UUID,
    heading_level: int,
) -> list[dict]:
    start_idx = next(i for i, n in enumerate(nodes) if n.node_id == heading_node_id)
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
    return body_blocks


def _collect_direct_body_blocks_from_parent(
    by_parent: dict[UUID | None, list[DocumentTreeNode]],
    heading_node_id: UUID,
) -> list[dict]:
    body_blocks: list[dict] = []
    for child in by_parent.get(heading_node_id, []):
        if child.node_type == DocumentTreeNodeType.heading:
            continue
        _append_body_block(body_blocks, child)
    return body_blocks


def _collect_body_blocks_until_next_heading(
    nodes: list[DocumentTreeNode],
    *,
    heading_node_id: UUID,
) -> list[dict]:
    """Collect non-heading nodes immediately after heading until the next heading row."""
    start_idx = next(i for i, n in enumerate(nodes) if n.node_id == heading_node_id)
    body_blocks: list[dict] = []
    idx = start_idx + 1
    while idx < len(nodes):
        node = nodes[idx]
        if node.node_type == DocumentTreeNodeType.heading:
            break
        _append_body_block(body_blocks, node)
        idx += 1
    return body_blocks


def build_section_direct_content(
    db: Session,
    *,
    document_id: UUID,
    heading_node_id: UUID,
) -> str:
    """Return only direct section body for a heading (no nested sub-heading bodies)."""
    nodes = (
        db.query(DocumentTreeNode)
        .filter(DocumentTreeNode.document_id == document_id)
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    heading = next((n for n in nodes if n.node_id == heading_node_id), None)
    if heading is None or heading.node_type != DocumentTreeNodeType.heading:
        return blocks_v1([])

    by_parent = _children_by_parent(nodes)
    body_blocks = _collect_direct_body_blocks_from_parent(by_parent, heading_node_id)
    if not body_blocks:
        body_blocks = _collect_body_blocks_until_next_heading(
            nodes,
            heading_node_id=heading_node_id,
        )

    return blocks_v1(body_blocks)


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

    heading_level = heading.level or 1
    by_parent = _children_by_parent(nodes)
    body_blocks = _collect_body_blocks_from_parent_tree(by_parent, heading_node_id)
    if not body_blocks:
        body_blocks = _collect_body_blocks_linear(
            nodes,
            heading_node_id=heading_node_id,
            heading_level=heading_level,
        )

    return blocks_v1(body_blocks)
