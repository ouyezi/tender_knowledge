from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.bid_outline_structure_diff import (
    BidOutlineStructureDiff,
    BidOutlineStructureDiffStatus,
)
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType


class BidOutlineDiffServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_title(value: str | None) -> str:
    return (value or "").strip().lower()


def _resolve_source_node_id(
    *,
    entry,
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


def _build_suggested_tree(
    db: Session,
    *,
    document_id: uuid.UUID,
    toc_entries: list,
    source_node_by_temp_id: dict[str, uuid.UUID] | None = None,
) -> list[dict]:
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

    suggested: list[dict] = []
    for entry in sorted(toc_entries, key=lambda item: int(getattr(item, "sort_order", 0) or 0)):
        source_node_id = _resolve_source_node_id(
            entry=entry,
            source_node_by_temp_id=source_node_by_temp_id,
            heading_index=heading_index,
        )
        suggested.append(
            {
                "temp_id": str(getattr(entry, "temp_id", "")),
                "parent_temp_id": (
                    str(getattr(entry, "parent_temp_id")) if getattr(entry, "parent_temp_id", None) else None
                ),
                "title": str(getattr(entry, "title", "")).strip() or "未命名章节",
                "level": max(int(getattr(entry, "level", 1) or 1), 1),
                "sort_order": max(int(getattr(entry, "sort_order", 0) or 0), 0),
                "source_node_id": str(source_node_id) if source_node_id else None,
                "needs_manual_review": source_node_id is None,
                "product_category_ids": [],
                "chapter_taxonomy_id": None,
            }
        )
    return suggested


def _build_structure_diff_payload(*, existing_nodes: list[BidOutlineNode], suggested_tree: list[dict]) -> dict:
    existing_map = {
        str(node.source_node_id) if node.source_node_id else f"legacy:{node.outline_node_id}": {
            "title": node.title,
            "level": node.level,
            "sort_order": node.sort_order,
            "parent_id": str(node.parent_id) if node.parent_id else None,
        }
        for node in existing_nodes
    }
    suggested_map = {
        str(item.get("source_node_id")) if item.get("source_node_id") else f"temp:{item.get('temp_id')}": {
            "title": str(item.get("title", "")),
            "level": int(item.get("level", 1) or 1),
            "sort_order": int(item.get("sort_order", 0) or 0),
            "parent_temp_id": str(item.get("parent_temp_id")) if item.get("parent_temp_id") else None,
        }
        for item in suggested_tree
    }
    added = [key for key in suggested_map if key not in existing_map]
    removed = [key for key in existing_map if key not in suggested_map]
    changed = []
    for key in suggested_map.keys() & existing_map.keys():
        old_item = existing_map[key]
        new_item = suggested_map[key]
        if (
            old_item["title"] != new_item["title"]
            or old_item["level"] != new_item["level"]
            or old_item["sort_order"] != new_item["sort_order"]
        ):
            changed.append({"key": key, "old": old_item, "new": new_item})
    return {
        "summary": {"added": len(added), "removed": len(removed), "changed": len(changed)},
        "added_keys": added,
        "removed_keys": removed,
        "changed_nodes": changed,
        "suggested_tree": suggested_tree,
    }


def generate_structure_diff(
    db: Session,
    *,
    kb_id: uuid.UUID,
    bid_outline_id: uuid.UUID,
    parse_task_id: uuid.UUID,
    document_id: uuid.UUID,
    toc_entries: list,
    source_node_by_temp_id: dict[str, uuid.UUID] | None = None,
) -> BidOutlineStructureDiff:
    suggested_tree = _build_suggested_tree(
        db,
        document_id=document_id,
        toc_entries=toc_entries,
        source_node_by_temp_id=source_node_by_temp_id,
    )
    existing_nodes = (
        db.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == bid_outline_id)
        .order_by(BidOutlineNode.level.asc(), BidOutlineNode.sort_order.asc(), BidOutlineNode.created_at.asc())
        .all()
    )
    diff_payload = _build_structure_diff_payload(existing_nodes=existing_nodes, suggested_tree=suggested_tree)
    diff = (
        db.query(BidOutlineStructureDiff)
        .filter(
            BidOutlineStructureDiff.kb_id == kb_id,
            BidOutlineStructureDiff.bid_outline_id == bid_outline_id,
            BidOutlineStructureDiff.parse_task_id == parse_task_id,
        )
        .one_or_none()
    )
    if diff is None:
        diff = BidOutlineStructureDiff(
            kb_id=kb_id,
            bid_outline_id=bid_outline_id,
            parse_task_id=parse_task_id,
        )
        db.add(diff)
    diff.diff_payload = diff_payload
    diff.status = BidOutlineStructureDiffStatus.pending
    diff.resolved_at = None
    diff.resolved_by = None
    db.flush()
    return diff


def apply_diff(
    db: Session,
    *,
    outline: BidOutline,
    diff: BidOutlineStructureDiff,
    operator_id: str,
) -> list[BidOutlineNode]:
    if diff.status != BidOutlineStructureDiffStatus.pending:
        raise BidOutlineDiffServiceError(
            "Only pending diff can be applied",
            code="DIFF_NOT_PENDING",
            status_code=409,
        )
    suggested_tree = (diff.diff_payload or {}).get("suggested_tree")
    if not isinstance(suggested_tree, list):
        raise BidOutlineDiffServiceError(
            "Diff payload missing suggested_tree",
            code="INVALID_STATE",
            status_code=422,
        )

    db.query(BidOutlineNode).filter(BidOutlineNode.bid_outline_id == outline.bid_outline_id).delete(
        synchronize_session=False
    )
    db.flush()

    created_by_temp: dict[str, BidOutlineNode] = {}
    parent_by_temp: dict[str, str | None] = {}
    for item in suggested_tree:
        temp_id = str(item.get("temp_id", "")).strip()
        if not temp_id:
            continue
        source_node_id = item.get("source_node_id")
        chapter_taxonomy_id = item.get("chapter_taxonomy_id")
        row = BidOutlineNode(
            kb_id=outline.kb_id,
            bid_outline_id=outline.bid_outline_id,
            parent_id=None,
            title=str(item.get("title", "")).strip() or "未命名章节",
            level=max(int(item.get("level", 1) or 1), 1),
            sort_order=max(int(item.get("sort_order", 0) or 0), 0),
            source_node_id=uuid.UUID(str(source_node_id)) if source_node_id else None,
            chapter_taxonomy_id=uuid.UUID(str(chapter_taxonomy_id)) if chapter_taxonomy_id else None,
            product_category_ids=item.get("product_category_ids") or [],
            needs_manual_review=bool(item.get("needs_manual_review", False)),
        )
        db.add(row)
        db.flush()
        created_by_temp[temp_id] = row
        parent_by_temp[temp_id] = str(item.get("parent_temp_id")) if item.get("parent_temp_id") else None

    for temp_id, row in created_by_temp.items():
        parent_temp = parent_by_temp.get(temp_id)
        if not parent_temp:
            continue
        parent = created_by_temp.get(parent_temp)
        if parent is not None:
            row.parent_id = parent.outline_node_id

    outline.updated_at = _now()
    diff.status = BidOutlineStructureDiffStatus.applied
    diff.resolved_by = operator_id
    diff.resolved_at = _now()
    db.flush()
    return (
        db.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == outline.bid_outline_id)
        .order_by(BidOutlineNode.level.asc(), BidOutlineNode.sort_order.asc(), BidOutlineNode.created_at.asc())
        .all()
    )


def reject_diff(
    db: Session,
    *,
    diff: BidOutlineStructureDiff,
    operator_id: str,
) -> BidOutlineStructureDiff:
    if diff.status != BidOutlineStructureDiffStatus.pending:
        raise BidOutlineDiffServiceError(
            "Only pending diff can be rejected",
            code="DIFF_NOT_PENDING",
            status_code=409,
        )
    diff.status = BidOutlineStructureDiffStatus.rejected
    diff.resolved_by = operator_id
    diff.resolved_at = _now()
    db.flush()
    return diff
