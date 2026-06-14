from __future__ import annotations

from dataclasses import dataclass

from src.services.docx_content_collector import RawBlock
from src.services.docx_hierarchy_inferrer import InferResult


@dataclass
class WalkedNode:
    temp_id: str
    parent_temp_id: str | None
    section_temp_id: str | None
    node_type: str
    text: str
    level: int
    sort_order: int
    source_block_index: int | None = None
    is_outline_node: bool = False
    needs_manual_review: bool = False


@dataclass
class MaterializedWalkResult:
    nodes: list[WalkedNode]
    used_flat_fallback: bool = False
    needs_manual_review: bool = False


def materialize_walk_result(blocks: list[RawBlock], inferred: InferResult) -> MaterializedWalkResult:
    nodes: list[WalkedNode] = []
    heading_temp_by_block: dict[int, str] = {}

    def append_node(**kwargs) -> WalkedNode:
        idx = len(nodes) + 1
        node = WalkedNode(temp_id=f"n{idx}", sort_order=idx - 1, **kwargs)
        nodes.append(node)
        return node

    if inferred.used_flat_fallback:
        for block in blocks:
            if block.block_type != "paragraph":
                continue
            append_node(
                parent_temp_id=None,
                section_temp_id=None,
                node_type="heading",
                text=block.text,
                level=1,
                source_block_index=block.index,
                is_outline_node=True,
                needs_manual_review=True,
            )
        return MaterializedWalkResult(nodes=nodes, used_flat_fallback=True, needs_manual_review=True)

    for heading in inferred.headings:
        parent_temp_id = (
            heading_temp_by_block.get(heading.parent_block_index)
            if heading.parent_block_index is not None
            else None
        )
        node = append_node(
            parent_temp_id=parent_temp_id,
            section_temp_id=None,
            node_type="heading",
            text=heading.title,
            level=heading.level,
            source_block_index=heading.block_index,
            is_outline_node=True,
            needs_manual_review=heading.confidence == "medium",
        )
        node.section_temp_id = node.temp_id
        heading_temp_by_block[heading.block_index] = node.temp_id

    heading_block_set = {h.block_index for h in inferred.headings}

    for block in blocks:
        if block.index in heading_block_set:
            continue
        section_temp_id = None
        for heading in reversed(inferred.headings):
            if heading.block_index < block.index:
                section_temp_id = heading_temp_by_block[heading.block_index]
                break
        node_type = block.block_type
        text = block.text
        if block.block_type == "paragraph" and block.has_image and not block.text:
            node_type = "image"
            text = "[image]"
        append_node(
            parent_temp_id=section_temp_id,
            section_temp_id=section_temp_id,
            node_type=node_type,
            text=text,
            level=0,
            source_block_index=block.index,
            is_outline_node=False,
            needs_manual_review=False,
        )

    needs_review = inferred.medium_confidence_count > 0
    return MaterializedWalkResult(
        nodes=nodes,
        used_flat_fallback=False,
        needs_manual_review=needs_review,
    )


def materialize_outline_nodes(inferred: InferResult, blocks: list[RawBlock]):
    from src.services.docx_outline_parser import OutlineNode

    if inferred.used_flat_fallback:
        paragraph_blocks = [b for b in blocks if b.block_type == "paragraph"]
        return [
            OutlineNode(
                temp_id=f"n{idx + 1}",
                parent_temp_id=None,
                title=b.text,
                level=1,
                sort_order=idx,
                needs_manual_review=True,
            )
            for idx, b in enumerate(paragraph_blocks)
        ]

    block_to_temp_id = {h.block_index: f"n{idx + 1}" for idx, h in enumerate(inferred.headings)}
    nodes: list[OutlineNode] = []
    for idx, heading in enumerate(inferred.headings):
        parent_temp_id = None
        if heading.parent_block_index is not None:
            parent_temp_id = block_to_temp_id.get(heading.parent_block_index)
        nodes.append(
            OutlineNode(
                temp_id=f"n{idx + 1}",
                parent_temp_id=parent_temp_id,
                title=heading.title,
                level=heading.level,
                sort_order=idx,
                needs_manual_review=heading.confidence == "medium",
            )
        )
    return nodes
