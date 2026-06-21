from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models.document import Document
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.doc_chunk.outline_heading_correction import apply_outline_heading_corrections
from src.services.doc_chunk.types import ImportContext
from src.services.text_sanitize import sanitize_pg_text

logger = logging.getLogger(__name__)


def _coerce_node_type(value: str | None) -> DocumentTreeNodeType:
    try:
        return DocumentTreeNodeType(value or "other")
    except ValueError:
        return DocumentTreeNodeType.other


def import_document_tree(
    db: Session,
    *,
    ctx: ImportContext,
    document: Document,
    kb_id: UUID,
    tree_payload: dict[str, Any],
    outline_payload: dict[str, Any] | None = None,
) -> dict[str, UUID]:
    nodes = list(tree_payload.get("nodes") or [])
    tree_id_map: dict[str, UUID] = {}
    outline_node_to_tree: dict[str, UUID] = {}
    db_nodes: list[DocumentTreeNode] = []

    for node in nodes:
        temp_id = str(node.get("node_id") or "").strip()
        if not temp_id:
            continue
        node_id = uuid4()
        tree_id_map[temp_id] = node_id
        outline_node_id = node.get("outline_node_id")
        if outline_node_id:
            outline_node_to_tree[str(outline_node_id)] = node_id

        node_type = _coerce_node_type(node.get("node_type"))
        safe_text = sanitize_pg_text(node.get("text"))
        title = sanitize_pg_text(node.get("title")) if node_type == DocumentTreeNodeType.heading else None
        if title:
            title = title[:512]
        content_ref = None
        if node_type == DocumentTreeNodeType.image:
            image_ref = str(node.get("image_ref") or "").strip()
            asset_id = ctx.image_ref_map.get(image_ref)
            if asset_id is not None:
                content_ref = str(asset_id)
            elif image_ref:
                content_ref = image_ref

        db_nodes.append(
            DocumentTreeNode(
                node_id=node_id,
                kb_id=kb_id,
                document_id=document.document_id,
                parent_id=None,
                node_type=node_type,
                title=title,
                level=int(node.get("level") or 0) or None,
                sort_order=max(int(node.get("sort_order") or 0), 0),
                content_ref=content_ref,
                content_preview=safe_text[:4000] if safe_text else None,
                chapter_taxonomy_id=None,
                product_category_ids=[],
                is_outline_node=node_type == DocumentTreeNodeType.heading and bool(outline_node_id),
                candidate_template_chapter_id=None,
                candidate_pattern_id=None,
                needs_manual_review=bool(node.get("needs_review")),
                tree_version=document.tree_version,
            )
        )

    db.add_all(db_nodes)
    db.flush()

    for node in nodes:
        temp_id = str(node.get("node_id") or "").strip()
        parent_temp = node.get("parent_id")
        if not temp_id or not parent_temp:
            continue
        child_id = tree_id_map.get(temp_id)
        parent_id = tree_id_map.get(str(parent_temp))
        if child_id is None or parent_id is None:
            continue
        db.query(DocumentTreeNode).filter(DocumentTreeNode.node_id == child_id).update(
            {"parent_id": parent_id},
            synchronize_session=False,
        )

    if outline_payload:
        corrected = apply_outline_heading_corrections(
            db,
            document_id=document.document_id,
            outline_payload=outline_payload,
            outline_node_to_tree_id=outline_node_to_tree,
        )
        logger.info(
            "import_document_tree outline corrections document_id=%s updated=%d",
            document.document_id,
            corrected,
        )

    db.flush()
    ctx.tree_id_map = tree_id_map
    ctx.outline_node_id_to_tree_id = outline_node_to_tree
    return tree_id_map
