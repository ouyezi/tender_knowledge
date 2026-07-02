from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.doc_chunk.linkage_validation import normalize_title
from src.services.text_sanitize import sanitize_pg_text

logger = logging.getLogger(__name__)


def _outline_nodes(outline_payload: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = outline_payload.get("nodes") or []
    return [node for node in nodes if isinstance(node, dict)]


def infer_outline_node_map_from_headings(
    outline_payload: dict[str, Any],
    headings: list[DocumentTreeNode],
    *,
    tree_payload: dict[str, Any] | None = None,
) -> dict[str, UUID]:
    """Match outline nodes to existing heading rows when persisted map is missing."""
    if tree_payload is not None:
        by_signature: dict[tuple[str, int | None, int], UUID] = {}
        for heading in headings:
            signature = (
                normalize_title(heading.title),
                heading.level,
                int(heading.sort_order),
            )
            by_signature.setdefault(signature, heading.node_id)

        mapping: dict[str, UUID] = {}
        for node in tree_payload.get("nodes") or []:
            if node.get("node_type") != "heading":
                continue
            outline_node_id = node.get("outline_node_id")
            if not outline_node_id:
                continue
            signature = (
                normalize_title(str(node.get("title") or "")),
                int(node.get("level") or 0) or None,
                int(node.get("sort_order") or 0),
            )
            tree_id = by_signature.get(signature)
            if tree_id is not None:
                mapping[str(outline_node_id)] = tree_id
        if mapping:
            return mapping

    outline_nodes = sorted(
        _outline_nodes(outline_payload),
        key=lambda item: int(item.get("sort_order") or 0),
    )
    db_headings = sorted(
        headings,
        key=lambda item: (int(item.sort_order), item.created_at),
    )
    if len(outline_nodes) != len(db_headings):
        logger.warning(
            "outline heading count mismatch outline=%d db=%d",
            len(outline_nodes),
            len(db_headings),
        )

    mapping = {}
    used: set[UUID] = set()
    for outline_node in outline_nodes:
        outline_node_id = str(outline_node.get("node_id") or "").strip()
        if not outline_node_id:
            continue
        target_title = normalize_title(str(outline_node.get("title") or ""))
        target_level = int(outline_node.get("level") or 0) or None
        match = None
        for heading in db_headings:
            if heading.node_id in used:
                continue
            if normalize_title(heading.title) != target_title:
                continue
            if target_level is not None and heading.level is not None and heading.level != target_level:
                continue
            match = heading
            break
        if match is None:
            continue
        mapping[outline_node_id] = match.node_id
        used.add(match.node_id)
    return mapping


def apply_outline_heading_corrections(
    db: Session,
    *,
    document_id: UUID,
    outline_payload: dict[str, Any],
    outline_node_to_tree_id: dict[str, UUID],
) -> int:
    """Align heading parent_id/level with outline.json for mapped outline nodes."""
    if not outline_payload or not outline_node_to_tree_id:
        return 0

    headings = (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.document_id == document_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .all()
    )
    headings_by_id = {item.node_id: item for item in headings}
    updated = 0

    for outline_node in _outline_nodes(outline_payload):
        outline_node_id = str(outline_node.get("node_id") or "").strip()
        if not outline_node_id:
            continue
        tree_node_id = outline_node_to_tree_id.get(outline_node_id)
        if tree_node_id is None:
            continue
        heading = headings_by_id.get(tree_node_id)
        if heading is None:
            logger.warning(
                "outline correction skipped missing heading document_id=%s outline_node_id=%s",
                document_id,
                outline_node_id,
            )
            continue

        desired_level = int(outline_node.get("level") or 0) or None
        outline_parent_id = outline_node.get("parent_id")
        desired_parent_id: UUID | None
        if outline_parent_id:
            desired_parent_id = outline_node_to_tree_id.get(str(outline_parent_id))
            if desired_parent_id is None:
                logger.warning(
                    "outline correction skipped missing parent document_id=%s "
                    "outline_node_id=%s parent_outline_id=%s",
                    document_id,
                    outline_node_id,
                    outline_parent_id,
                )
                continue
        else:
            desired_parent_id = None

        changed = False
        if heading.parent_id != desired_parent_id:
            logger.info(
                "outline heading parent corrected document_id=%s title=%r "
                "outline_node_id=%s old_parent=%s new_parent=%s",
                document_id,
                heading.title,
                outline_node_id,
                heading.parent_id,
                desired_parent_id,
            )
            heading.parent_id = desired_parent_id
            changed = True
        if desired_level is not None and heading.level != desired_level:
            logger.info(
                "outline heading level corrected document_id=%s title=%r "
                "outline_node_id=%s old_level=%s new_level=%s",
                document_id,
                heading.title,
                outline_node_id,
                heading.level,
                desired_level,
            )
            heading.level = desired_level
            changed = True
        desired_title = sanitize_pg_text(str(outline_node.get("title") or ""))
        if desired_title and heading.title != desired_title:
            safe_title = desired_title[:512]
            logger.info(
                "outline heading title corrected document_id=%s outline_node_id=%s old_title=%r new_title=%r",
                document_id,
                outline_node_id,
                heading.title,
                safe_title,
            )
            heading.title = safe_title
            changed = True
        outline_sort = outline_node.get("sort_order")
        if outline_sort is not None:
            desired_sort = int(outline_sort)
            if heading.sort_order != desired_sort:
                logger.info(
                    "outline heading sort_order corrected document_id=%s title=%r "
                    "outline_node_id=%s old_sort=%s new_sort=%s",
                    document_id,
                    heading.title,
                    outline_node_id,
                    heading.sort_order,
                    desired_sort,
                )
                heading.sort_order = desired_sort
                changed = True
        if changed:
            updated += 1

    if updated:
        db.flush()
    logger.info(
        "outline heading corrections applied document_id=%s updated=%d mapped=%d",
        document_id,
        updated,
        len(outline_node_to_tree_id),
    )
    return updated
