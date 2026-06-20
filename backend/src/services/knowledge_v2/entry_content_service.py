from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists
from sqlalchemy.orm import Session

from src.models.chunk_asset import ChunkAsset
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.doc_chunk.content_md_store import load_content_md
from src.services.doc_chunk.section_slice import outline_nodes_from_tree_nodes, slice_section_markdown
from src.services.knowledge_v2.asset_link_service import assets_in_range
from src.services.knowledge_v2.media_url_service import (
    load_image_ref_map_payload,
    resolve_storage_path_to_media_url,
)


class DocumentNotFoundError(Exception):
    pass


class NodeNotFoundError(Exception):
    pass


class ContentNotAvailableError(Exception):
    pass


def knowledge_source_type_for_document(document: Document) -> str:
    if document.source_type == DocumentSourceType.template_file:
        return "template"
    return "bid"


def list_entry_documents(db: Session, kb_id: UUID) -> list[Document]:
    has_tree_nodes = exists().where(
        and_(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == Document.document_id,
        )
    )
    return (
        db.query(Document)
        .filter(
            Document.kb_id == kb_id,
            Document.parse_status == DocumentParseStatus.ready,
            has_tree_nodes,
        )
        .order_by(Document.updated_at.desc())
        .all()
    )


def get_document_tree(db: Session, kb_id: UUID, doc_id: UUID) -> list[dict]:
    _get_ready_document(db, kb_id=kb_id, doc_id=doc_id)
    nodes = _load_heading_nodes(db, kb_id=kb_id, doc_id=doc_id)
    node_ids = [str(node.node_id) for node in nodes]
    ingested_node_ids: set[str] = set()
    if node_ids:
        ingested_node_ids = {
            node_id
            for (node_id,) in (
                db.query(KnowledgeChunk.primary_node_id)
                .filter(
                    KnowledgeChunk.kb_id == kb_id,
                    KnowledgeChunk.doc_id == doc_id,
                    KnowledgeChunk.is_latest.is_(True),
                    KnowledgeChunk.primary_node_id.in_(node_ids),
                )
                .all()
            )
        }
    return _build_tree_payload(nodes, ingested_node_ids=ingested_node_ids)


def get_node_preview(db: Session, kb_id: UUID, doc_id: UUID, node_id: UUID) -> dict:
    _get_ready_document(db, kb_id=kb_id, doc_id=doc_id)
    nodes = _load_heading_nodes(db, kb_id=kb_id, doc_id=doc_id)
    nodes_by_id = {node.node_id: node for node in nodes}
    node = nodes_by_id.get(node_id)
    if node is None:
        raise NodeNotFoundError

    content_md = load_content_md(document_id=doc_id)
    if not content_md:
        raise ContentNotAvailableError

    section_md = slice_section_markdown(
        content_md,
        outline_nodes_from_tree_nodes(nodes),
        str(node_id),
    )
    if not section_md or not section_md.strip():
        raise ContentNotAvailableError

    subtree_ids = _collect_subtree_node_ids(nodes, root_id=node_id)
    chunks = (
        db.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.doc_id == doc_id,
            KnowledgeChunk.is_latest.is_(True),
            KnowledgeChunk.primary_node_id.in_([str(item) for item in subtree_ids]),
        )
        .all()
    )
    chunk_char_start, chunk_char_end = _range_from_chunks(chunks)
    slice_char_start, slice_char_end = _range_from_slice(content_md, section_md)
    char_start = chunk_char_start if chunk_char_start is not None else slice_char_start
    char_end = chunk_char_end if chunk_char_end is not None else slice_char_end

    assets = (
        db.query(ChunkAsset)
        .filter(ChunkAsset.kb_id == kb_id, ChunkAsset.doc_id == doc_id)
        .order_by(ChunkAsset.char_start.asc(), ChunkAsset.id.asc())
        .all()
    )
    matched_assets = assets_in_range(assets, char_start=char_start, char_end=char_end)
    page_start, page_end = _page_range(chunks, matched_assets)

    return {
        "title": node.title or "",
        "content_md": section_md,
        "content_type": infer_content_type(section_md, matched_assets),
        "char_start": char_start,
        "char_end": char_end,
        "page_start": page_start,
        "page_end": page_end,
        "catalog_path": build_catalog_path(nodes_by_id, node_id),
        "assets": [_serialize_asset(item, db, kb_id=kb_id) for item in matched_assets],
        "image_ref_map": load_image_ref_map_payload(document_id=doc_id),
    }


def build_catalog_path(nodes_by_id: dict, node_id: UUID) -> list[dict]:
    path: list[dict] = []
    current = nodes_by_id.get(node_id)
    while current is not None:
        path.append(
            {
                "node_id": str(current.node_id),
                "title": current.title or "",
                "level": int(current.level or 1),
            }
        )
        parent_id = getattr(current, "parent_id", None)
        if parent_id is None:
            break
        current = nodes_by_id.get(parent_id)
    path.reverse()
    return path


def infer_content_type(content_md: str, assets: list) -> str:
    if assets:
        return "mixed"
    markdown = (content_md or "").lower()
    if "![" in markdown or "<img" in markdown:
        return "mixed"
    if re.search(r"(?m)^\|.*\|\s*$", markdown):
        return "mixed"
    return "text"


def _get_ready_document(db: Session, *, kb_id: UUID, doc_id: UUID) -> Document:
    document = (
        db.query(Document)
        .filter(
            Document.kb_id == kb_id,
            Document.document_id == doc_id,
            Document.parse_status == DocumentParseStatus.ready,
        )
        .one_or_none()
    )
    if document is None:
        raise DocumentNotFoundError
    return document


def _load_heading_nodes(db: Session, *, kb_id: UUID, doc_id: UUID) -> list[DocumentTreeNode]:
    return (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == doc_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(
            DocumentTreeNode.sort_order.asc(),
            DocumentTreeNode.level.asc(),
            DocumentTreeNode.created_at.asc(),
        )
        .all()
    )


def _build_tree_payload(
    nodes: list[DocumentTreeNode], *, ingested_node_ids: set[str]
) -> list[dict[str, Any]]:
    children_by_parent: dict[UUID | None, list[DocumentTreeNode]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node)
    for children in children_by_parent.values():
        children.sort(key=lambda item: (item.sort_order, item.created_at))

    def build(node: DocumentTreeNode) -> dict[str, Any]:
        return {
            "node_id": str(node.node_id),
            "title": node.title or "",
            "parent_id": str(node.parent_id) if node.parent_id else None,
            "level": int(node.level or 1),
            "sort_order": int(node.sort_order),
            "ingested": str(node.node_id) in ingested_node_ids,
            "children": [build(child) for child in children_by_parent.get(node.node_id, [])],
        }

    roots = children_by_parent.get(None, [])
    return [build(root) for root in roots]


def _collect_subtree_node_ids(nodes: list[DocumentTreeNode], *, root_id: UUID) -> list[UUID]:
    children_by_parent: dict[UUID | None, list[UUID]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node.node_id)
    ordered: list[UUID] = []
    stack = [root_id]
    while stack:
        current = stack.pop()
        ordered.append(current)
        children = children_by_parent.get(current, [])
        stack.extend(reversed(children))
    return ordered


def _range_from_chunks(chunks: list[KnowledgeChunk]) -> tuple[int | None, int | None]:
    starts = [item.char_start for item in chunks if item.char_start is not None]
    ends = [item.char_end for item in chunks if item.char_end is not None]
    if not starts or not ends:
        return (None, None)
    return (min(starts), max(ends))


def _range_from_slice(content_md: str, section_md: str) -> tuple[int | None, int | None]:
    start = content_md.find(section_md)
    if start < 0:
        return (None, None)
    return (start, start + len(section_md))


def _page_range(
    chunks: list[KnowledgeChunk],
    assets: list[ChunkAsset],
) -> tuple[int | None, int | None]:
    page_starts = [item.page_start for item in chunks if item.page_start is not None]
    page_ends = [item.page_end for item in chunks if item.page_end is not None]
    if page_starts and page_ends:
        return (min(page_starts), max(page_ends))
    asset_page_starts = [item.page_start for item in assets if item.page_start is not None]
    asset_page_ends = [item.page_end for item in assets if item.page_end is not None]
    if asset_page_starts and asset_page_ends:
        return (min(asset_page_starts), max(asset_page_ends))
    return (None, None)


def _serialize_asset(asset: ChunkAsset, db: Session, *, kb_id: UUID) -> dict[str, Any]:
    image_storage_url = asset.image_storage_url
    if asset.asset_type == "image":
        image_storage_url = resolve_storage_path_to_media_url(
            db,
            kb_id=kb_id,
            storage_path=asset.image_storage_url,
        )
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "asset_code": asset.asset_code,
        "char_start": asset.char_start,
        "char_end": asset.char_end,
        "page_start": asset.page_start,
        "page_end": asset.page_end,
        "raw_markdown": asset.raw_markdown,
        "image_storage_url": image_storage_url,
    }
