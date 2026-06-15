from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.bid_outline import BidOutlineExtractStrategy
from src.services import bid_outline_extract_service
from src.services.bid_outline_extract_service import PersistedOutlineResult
from src.services.doc_chunk.types import ImportContext, OutlineTocEntry


_STRATEGY_MAP = {
    "toc": BidOutlineExtractStrategy.toc,
    "heading_heuristic": BidOutlineExtractStrategy.heading_heuristic,
    "content_heuristic": BidOutlineExtractStrategy.content_heuristic,
    "flat_fallback": BidOutlineExtractStrategy.flat_fallback,
}


def map_outline_strategy(raw: str | None) -> BidOutlineExtractStrategy:
    if raw == "doc_chunk":
        return BidOutlineExtractStrategy.doc_chunk
    return _STRATEGY_MAP.get(str(raw or "").strip(), BidOutlineExtractStrategy.doc_chunk)


def build_toc_entries(
    *,
    outline_payload: dict[str, Any],
    linkage_payload: dict[str, Any],
    ctx: ImportContext,
) -> tuple[list[OutlineTocEntry], dict[str, UUID]]:
    outline_nodes = {str(n.get("node_id")): n for n in (outline_payload.get("nodes") or [])}
    linkage_by_outline = {
        str(entry.get("outline_node_id")): entry for entry in (linkage_payload.get("entries") or [])
    }

    source_node_by_temp_id: dict[str, UUID] = {}
    toc_entries: list[OutlineTocEntry] = []

    for outline_id, node in outline_nodes.items():
        linkage = linkage_by_outline.get(outline_id) or {}
        tree_ids = [str(item) for item in (linkage.get("document_tree_node_ids") or [])]
        source_node_id = None
        if tree_ids:
            source_node_id = ctx.tree_id_map.get(tree_ids[0])
        if source_node_id is None:
            source_node_id = ctx.outline_node_id_to_tree_id.get(outline_id)
        if source_node_id is not None:
            source_node_by_temp_id[outline_id] = source_node_id

        parent_id = node.get("parent_id")
        toc_entries.append(
            OutlineTocEntry(
                temp_id=outline_id,
                parent_temp_id=str(parent_id) if parent_id else None,
                title=str(node.get("title") or "未命名章节"),
                level=max(int(node.get("level") or 1), 1),
                sort_order=int(node.get("sort_order") or 0),
                source_node_id=source_node_id,
            )
        )

    toc_entries.sort(key=lambda item: item.sort_order)
    return toc_entries, source_node_by_temp_id


def import_bid_outline(
    db: Session,
    *,
    ctx: ImportContext,
    kb_id: UUID,
    import_id: UUID,
    document_id: UUID,
    outline_name: str,
    outline_payload: dict[str, Any],
    linkage_payload: dict[str, Any],
    created_by: str = "system",
    product_category_ids: list[Any] | None = None,
    project_name: str | None = None,
    customer_name: str | None = None,
) -> PersistedOutlineResult:
    toc_entries, source_node_by_temp_id = build_toc_entries(
        outline_payload=outline_payload,
        linkage_payload=linkage_payload,
        ctx=ctx,
    )
    extract_strategy = map_outline_strategy(outline_payload.get("strategy"))
    return bid_outline_extract_service.persist_outline(
        db,
        kb_id=kb_id,
        import_id=import_id,
        document_id=document_id,
        outline_name=outline_name,
        toc_entries=toc_entries,
        source_node_by_temp_id=source_node_by_temp_id,
        created_by=created_by,
        extract_strategy=extract_strategy,
        product_category_ids=product_category_ids or [],
        project_name=project_name,
        customer_name=customer_name,
    )
