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
from src.models.knowledge_blueprint import KnowledgeBlueprint
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.doc_chunk.content_md_store import load_content_md
from src.services.doc_chunk.outline_store import load_outline, resolve_outline_node_id
from src.services.doc_chunk.section_slice import (
    PREFACE_NODE_ID,
    PREFACE_TITLE,
    is_preface_node_id,
    slice_section_by_anchor,
)
from src.services.knowledge.asset_section_utils import filter_assets_for_section
from src.services.knowledge.media_url_service import (
    load_image_ref_map_payload,
    resolve_storage_paths_to_media_urls,
)

_HEADING_RE = re.compile(r"^(#{1,8})[ \t]+(.+?)[ \t#]*$", re.MULTILINE)


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
    node_uuids = [node.node_id for node in nodes]
    node_ids = [str(node_id) for node_id in node_uuids]
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
    blueprint_node_ids: set[str] = set()
    if node_uuids:
        blueprint_node_ids = {
            str(source_node_id)
            for (source_node_id,) in (
                db.query(KnowledgeBlueprint.source_node_id)
                .filter(
                    KnowledgeBlueprint.kb_id == kb_id,
                    KnowledgeBlueprint.source_doc_id == doc_id,
                    KnowledgeBlueprint.source_node_id.in_(node_uuids),
                )
                .all()
            )
        }
    tree = _build_tree_payload(
        nodes,
        ingested_node_ids=ingested_node_ids,
        blueprint_node_ids=blueprint_node_ids,
    )
    content_md = load_content_md(document_id=doc_id)
    if content_md and _has_preface_content(content_md):
        return [_build_preface_tree_node(), *tree]
    return tree


def get_node_preview(db: Session, kb_id: UUID, doc_id: UUID, node_id: UUID | str) -> dict:
    _get_ready_document(db, kb_id=kb_id, doc_id=doc_id)
    nodes = _load_heading_nodes(db, kb_id=kb_id, doc_id=doc_id)
    content_md = load_content_md(document_id=doc_id)
    if not content_md:
        raise ContentNotAvailableError

    outline_payload = load_outline(document_id=doc_id)
    if not outline_payload:
        raise ContentNotAvailableError

    node_key = str(node_id)
    if is_preface_node_id(node_key):
        if not _has_preface_content(content_md):
            raise NodeNotFoundError
        section_md = slice_section_by_anchor(content_md, outline_payload, PREFACE_NODE_ID)
        if not section_md or not section_md.strip():
            raise ContentNotAvailableError
        slice_char_start, slice_char_end = _range_from_slice(content_md, section_md)
        matched_assets = _query_assets_in_range(
            db,
            kb_id=kb_id,
            doc_id=doc_id,
            char_start=slice_char_start,
            char_end=slice_char_end,
        )
        matched_assets = filter_assets_for_section(matched_assets, section_md)
        return {
            "title": PREFACE_TITLE,
            "content_md": section_md,
            "content_type": infer_content_type(section_md, matched_assets),
            "char_start": slice_char_start,
            "char_end": slice_char_end,
            "page_start": None,
            "page_end": None,
            "catalog_path": _build_preface_catalog_path(),
            "assets": _serialize_assets(matched_assets, db, kb_id=kb_id),
            "image_ref_map": load_image_ref_map_payload(document_id=doc_id),
        }

    node_uuid = _coerce_tree_node_id(node_key)
    nodes_by_id = {node.node_id: node for node in nodes}
    node = nodes_by_id.get(node_uuid)
    if node is None:
        raise NodeNotFoundError

    outline_node_id = resolve_outline_node_id(document_id=doc_id, tree_node_id=node_uuid)
    if not outline_node_id:
        raise NodeNotFoundError
    section_md = slice_section_by_anchor(content_md, outline_payload, outline_node_id)
    if not section_md or not section_md.strip():
        raise ContentNotAvailableError

    subtree_ids = _collect_subtree_node_ids(nodes, root_id=node_uuid)
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

    matched_assets = _query_assets_in_range(
        db,
        kb_id=kb_id,
        doc_id=doc_id,
        char_start=char_start,
        char_end=char_end,
    )
    matched_assets = filter_assets_for_section(matched_assets, section_md)
    page_start, page_end = _page_range(chunks, matched_assets)

    return {
        "title": node.title or "",
        "content_md": section_md,
        "content_type": infer_content_type(section_md, matched_assets),
        "char_start": char_start,
        "char_end": char_end,
        "page_start": page_start,
        "page_end": page_end,
        "catalog_path": build_catalog_path(nodes_by_id, node_uuid),
        "assets": _serialize_assets(matched_assets, db, kb_id=kb_id),
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


def _first_heading_char_start(content_md: str) -> int | None:
    match = _HEADING_RE.search(content_md)
    return match.start() if match else None


def _has_preface_content(content_md: str) -> bool:
    first_heading = _first_heading_char_start(content_md)
    if first_heading is None:
        return False
    return bool(content_md[:first_heading].strip())


def _build_preface_tree_node() -> dict[str, Any]:
    return {
        "node_id": PREFACE_NODE_ID,
        "title": PREFACE_TITLE,
        "parent_id": None,
        "level": 0,
        "sort_order": -1,
        "ingested": False,
        "has_blueprint": False,
        "children": [],
    }


def _build_preface_catalog_path() -> list[dict[str, Any]]:
    return [
        {
            "node_id": PREFACE_NODE_ID,
            "title": PREFACE_TITLE,
            "level": 0,
        }
    ]


def _coerce_tree_node_id(node_id: str) -> UUID:
    try:
        return UUID(node_id)
    except ValueError as exc:
        raise NodeNotFoundError from exc


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
    nodes: list[DocumentTreeNode],
    *,
    ingested_node_ids: set[str],
    blueprint_node_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    blueprint_node_ids = blueprint_node_ids or set()
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
            "has_blueprint": str(node.node_id) in blueprint_node_ids,
            "children": [build(child) for child in children_by_parent.get(node.node_id, [])],
        }

    roots = children_by_parent.get(None, [])
    roots.sort(key=lambda item: (item.sort_order, item.created_at))
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


def compute_section_char_range(
    db: Session,
    *,
    kb_id: UUID,
    doc_id: UUID,
    primary_node_id: UUID,
    content: str,
) -> tuple[int | None, int | None]:
    _ = (db, kb_id, primary_node_id)
    content_md = load_content_md(document_id=doc_id)
    if not content_md:
        return (None, None)
    section_md = content.strip()
    if not section_md:
        return (None, None)
    return _range_from_slice(content_md, section_md)


def _page_range(
    chunks: list[KnowledgeChunk],
    assets: list[ChunkAsset],
) -> tuple[int | None, int | None]:
    _ = chunks
    asset_page_starts = [item.page_start for item in assets if item.page_start is not None]
    asset_page_ends = [item.page_end for item in assets if item.page_end is not None]
    if asset_page_starts and asset_page_ends:
        return (min(asset_page_starts), max(asset_page_ends))
    return (None, None)


def _query_assets_in_range(
    db: Session,
    *,
    kb_id: UUID,
    doc_id: UUID,
    char_start: int | None,
    char_end: int | None,
) -> list[ChunkAsset]:
    if char_start is None or char_end is None:
        return []
    return (
        db.query(ChunkAsset)
        .filter(
            ChunkAsset.kb_id == kb_id,
            ChunkAsset.doc_id == doc_id,
            ChunkAsset.char_start.isnot(None),
            ChunkAsset.char_end.isnot(None),
            ChunkAsset.char_start < char_end,
            ChunkAsset.char_end > char_start,
        )
        .order_by(ChunkAsset.char_start.asc(), ChunkAsset.id.asc())
        .all()
    )


def _serialize_assets(assets: list[ChunkAsset], db: Session, *, kb_id: UUID) -> list[dict[str, Any]]:
    image_paths = [
        asset.image_storage_url
        for asset in assets
        if asset.asset_type == "image" and asset.image_storage_url
    ]
    media_url_map = resolve_storage_paths_to_media_urls(db, kb_id=kb_id, storage_paths=image_paths)
    return [_serialize_asset(asset, media_url_map) for asset in assets]


def _serialize_asset(asset: ChunkAsset, media_url_map: dict[str, str]) -> dict[str, Any]:
    image_storage_url = asset.image_storage_url
    if asset.asset_type == "image" and image_storage_url:
        image_storage_url = media_url_map.get(image_storage_url, image_storage_url)
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
