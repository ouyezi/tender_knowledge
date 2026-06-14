from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from sqlalchemy.orm import Session

from src.models.bid_outline import BidOutline, BidOutlineExtractStrategy
from src.models.bid_outline_node import BidOutlineNode
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.text_sanitize import sanitize_pg_text


@dataclass
class PersistedOutlineResult:
    bid_outline: BidOutline
    node_count: int


def _normalize_title(value: str | None) -> str:
    return (value or "").strip().lower()


def _coerce_strategy(value: str | BidOutlineExtractStrategy | None) -> BidOutlineExtractStrategy:
    if isinstance(value, BidOutlineExtractStrategy):
        return value
    if isinstance(value, str):
        try:
            return BidOutlineExtractStrategy(value)
        except ValueError:
            pass
    return BidOutlineExtractStrategy.heading_heuristic


def _resolve_source_node_id(
    *,
    entry: Any,
    source_node_by_temp_id: dict[str, uuid.UUID] | None,
    heading_index: dict[tuple[int, str], list[uuid.UUID]],
) -> uuid.UUID | None:
    source_node_id = getattr(entry, "source_node_id", None)
    if source_node_id is not None:
        return source_node_id

    temp_id = str(getattr(entry, "temp_id", "")).strip()
    if source_node_by_temp_id and temp_id in source_node_by_temp_id:
        return source_node_by_temp_id[temp_id]

    key = (int(getattr(entry, "level", 1) or 1), _normalize_title(getattr(entry, "title", None)))
    candidates = heading_index.get(key) or []
    if not candidates:
        return None
    return candidates.pop(0)


def persist_outline(
    db: Session,
    *,
    kb_id: uuid.UUID,
    import_id: uuid.UUID,
    document_id: uuid.UUID,
    outline_name: str,
    toc_entries: list[Any],
    source_node_by_temp_id: dict[str, uuid.UUID] | None = None,
    created_by: str = "system",
    extract_strategy: str | BidOutlineExtractStrategy | None = None,
    product_category_ids: list[Any] | None = None,
    project_name: str | None = None,
    customer_name: str | None = None,
) -> PersistedOutlineResult:
    strategy = _coerce_strategy(extract_strategy)
    outline = (
        db.query(BidOutline)
        .filter(BidOutline.kb_id == kb_id, BidOutline.source_doc_id == document_id)
        .order_by(BidOutline.created_at.desc())
        .first()
    )
    if outline is None:
        outline = BidOutline(
            kb_id=kb_id,
            source_doc_id=document_id,
            import_id=import_id,
            outline_name=outline_name,
            created_by=created_by,
        )
        db.add(outline)
        db.flush()

    outline.outline_name = outline_name
    outline.extract_strategy = strategy
    outline.product_category_ids = product_category_ids or []
    outline.project_name = project_name
    outline.customer_name = customer_name

    db.query(BidOutlineNode).filter(BidOutlineNode.bid_outline_id == outline.bid_outline_id).delete(
        synchronize_session=False
    )
    db.flush()

    headings = (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.document_id == document_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    heading_index: dict[tuple[int, str], list[uuid.UUID]] = {}
    for node in headings:
        key = (int(node.level or 1), _normalize_title(node.title))
        heading_index.setdefault(key, []).append(node.node_id)

    parent_map: dict[str, uuid.UUID] = {}
    created_nodes: list[BidOutlineNode] = []
    for entry in sorted(toc_entries, key=lambda item: int(getattr(item, "sort_order", 0) or 0)):
        temp_id = str(getattr(entry, "temp_id"))
        parent_temp_id = getattr(entry, "parent_temp_id", None)
        parent_id = parent_map.get(str(parent_temp_id)) if parent_temp_id else None
        source_node_id = _resolve_source_node_id(
            entry=entry,
            source_node_by_temp_id=source_node_by_temp_id,
            heading_index=heading_index,
        )
        raw_title = sanitize_pg_text(str(getattr(entry, "title", "")).strip()) or "未命名章节"
        node = BidOutlineNode(
            kb_id=kb_id,
            bid_outline_id=outline.bid_outline_id,
            parent_id=parent_id,
            title=raw_title[:512],
            level=max(int(getattr(entry, "level", 1) or 1), 1),
            sort_order=max(int(getattr(entry, "sort_order", 0) or 0), 0),
            source_node_id=source_node_id,
            product_category_ids=[],
            needs_manual_review=source_node_id is None,
        )
        db.add(node)
        parent_map[temp_id] = node.outline_node_id
        created_nodes.append(node)

    db.flush()
    return PersistedOutlineResult(bid_outline=outline, node_count=len(created_nodes))
