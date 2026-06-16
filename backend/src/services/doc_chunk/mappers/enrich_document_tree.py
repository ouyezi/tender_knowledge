from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models.document import Document
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.doc_chunk.linkage_validation import chunk_matches_outline_entry, titles_compatible
from src.services.doc_chunk.types import ImportContext
from src.services.doc_chunk.workspace_loader import load_chunk_file


def _heading_has_body_children(db: Session, *, heading_node_id: UUID) -> bool:
    return (
        db.query(DocumentTreeNode.node_id)
        .filter(
            DocumentTreeNode.parent_id == heading_node_id,
            DocumentTreeNode.node_type != DocumentTreeNodeType.heading,
        )
        .first()
        is not None
    )


def _sort_order_for_enriched_block(*, heading: DocumentTreeNode, index: int) -> int:
    return heading.sort_order * 1000 + index + 1


def _materialize_chunk_blocks(
    db: Session,
    *,
    document: Document,
    kb_id: UUID,
    heading: DocumentTreeNode,
    blocks: list[dict[str, Any]],
    image_ref_map: dict[str, UUID],
) -> int:
    created = 0
    for index, block in enumerate(blocks):
        block_type = str(block.get("type") or "")
        node_type = DocumentTreeNodeType.other
        content_preview = None
        content_ref = None
        if block_type in {"paragraph", "table"}:
            node_type = (
                DocumentTreeNodeType.paragraph
                if block_type == "paragraph"
                else DocumentTreeNodeType.table
            )
            text = str(block.get("text") or "").strip()
            if not text:
                continue
            content_preview = text[:4000]
        elif block_type == "image":
            node_type = DocumentTreeNodeType.image
            image_ref = str(block.get("image_ref") or "").strip()
            asset_id = image_ref_map.get(image_ref)
            if asset_id is not None:
                content_ref = str(asset_id)
            elif image_ref:
                content_ref = image_ref
        else:
            continue

        db.add(
            DocumentTreeNode(
                node_id=uuid4(),
                kb_id=kb_id,
                document_id=document.document_id,
                parent_id=heading.node_id,
                node_type=node_type,
                title=None,
                level=None,
                sort_order=_sort_order_for_enriched_block(heading=heading, index=index),
                content_ref=content_ref,
                content_preview=content_preview,
                chapter_taxonomy_id=None,
                product_category_ids=[],
                is_outline_node=False,
                candidate_template_chapter_id=None,
                candidate_pattern_id=None,
                needs_manual_review=False,
                tree_version=document.tree_version,
            )
        )
        created += 1
    if created:
        db.flush()
    return created


def enrich_document_tree_from_chunks(
    db: Session,
    *,
    ctx: ImportContext,
    document: Document,
    kb_id: UUID,
    linkage_payload: dict[str, Any],
    chunks_index: dict[str, Any],
    warnings: list[str],
) -> int:
    chunk_path_by_id = {
        str(item.get("chunk_id")): str(item.get("path"))
        for item in (chunks_index.get("chunks") or [])
        if item.get("chunk_id") and item.get("path")
    }
    enriched = 0

    for entry in linkage_payload.get("entries") or []:
        tree_ids = [str(item) for item in (entry.get("document_tree_node_ids") or [])]
        if not tree_ids:
            continue
        primary_chunk_id = entry.get("primary_chunk_id")
        if not primary_chunk_id:
            chunk_ids = [str(item) for item in (entry.get("chunk_ids") or [])]
            primary_chunk_id = chunk_ids[0] if chunk_ids else None
        if not primary_chunk_id:
            continue

        heading_id = ctx.tree_id_map.get(tree_ids[0])
        if heading_id is None:
            continue
        heading = db.get(DocumentTreeNode, heading_id)
        if heading is None or heading.node_type != DocumentTreeNodeType.heading:
            continue
        if _heading_has_body_children(db, heading_node_id=heading.node_id):
            continue

        rel_path = chunk_path_by_id.get(str(primary_chunk_id))
        if not rel_path:
            warnings.append(f"enrich_missing_chunk:{primary_chunk_id}")
            continue

        chunk_payload = load_chunk_file(ctx.workspace_path, f"chunks/{rel_path}")
        outline_node_id = str(entry.get("outline_node_id") or "")
        if not chunk_matches_outline_entry(
            outline_node_id=outline_node_id or None,
            chunk_payload=chunk_payload,
        ):
            warnings.append(
                f"enrich_chunk_outline_mismatch:{primary_chunk_id}:{outline_node_id}"
            )
            continue

        chunk_title = str(chunk_payload.get("title") or "").strip()
        if not titles_compatible(heading.title, chunk_title):
            warnings.append(
                f"enrich_chunk_title_mismatch:{primary_chunk_id}:{heading.title}:{chunk_title}"
            )
            continue

        blocks = chunk_payload.get("blocks") or []
        if not blocks:
            continue
        enriched += _materialize_chunk_blocks(
            db,
            document=document,
            kb_id=kb_id,
            heading=heading,
            blocks=blocks,
            image_ref_map=ctx.image_ref_map,
        )

    return enriched
