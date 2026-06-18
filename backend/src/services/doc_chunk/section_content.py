from __future__ import annotations

from typing import Any

from src.services.doc_chunk.markdown_blocks import markdown_to_blocks
from src.services.doc_chunk.section_slice import (
    outline_nodes_from_bid_nodes,
    outline_nodes_from_payload,
    slice_section_markdown,
)


def section_blocks_for_outline_node(
    content_md: str,
    outline_payload: dict[str, Any],
    outline_node_id: str,
) -> list[dict[str, Any]]:
    markdown = slice_section_markdown(
        content_md,
        outline_nodes_from_payload(outline_payload),
        outline_node_id,
    )
    if not markdown or not markdown.strip():
        return []
    return markdown_to_blocks(markdown)


def section_blocks_for_bid_outline_node(
    content_md: str,
    bid_outline_nodes: list[Any],
    outline_node_id: str,
) -> list[dict[str, Any]]:
    markdown = slice_section_markdown(
        content_md,
        outline_nodes_from_bid_nodes(bid_outline_nodes),
        outline_node_id,
    )
    if not markdown or not markdown.strip():
        return []
    return markdown_to_blocks(markdown)
