from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.chunk_asset import ChunkAsset
from src.models.document_media_asset import DocumentMediaAsset
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.doc_chunk.blocks_v1 import resolve_image_asset_id
from src.services.doc_chunk.content_md_store import load_image_ref_map

_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def parse_markdown_image_refs(content: str) -> list[tuple[str, int, int]]:
    refs: list[tuple[str, int, int]] = []
    for match in _MARKDOWN_IMAGE_RE.finditer(content or ""):
        image_ref = match.group(1).strip().replace("\\", "/")
        if image_ref:
            refs.append((image_ref, match.start(), match.end()))
    return refs


def resolve_image_ref_storage_path(
    db: Session,
    *,
    kb_id: UUID,
    doc_id: UUID,
    image_ref: str,
    image_ref_map: dict[str, UUID],
) -> str | None:
    asset_id = resolve_image_asset_id(image_ref, image_ref_map)
    if asset_id is None:
        return None
    row = (
        db.query(DocumentMediaAsset.storage_path)
        .filter(
            DocumentMediaAsset.kb_id == kb_id,
            DocumentMediaAsset.document_id == doc_id,
            DocumentMediaAsset.asset_id == asset_id,
        )
        .one_or_none()
    )
    return row[0] if row else None


def ensure_image_assets_for_chunk(db: Session, chunk: KnowledgeChunk) -> list[ChunkAsset]:
    image_ref_map = load_image_ref_map(document_id=chunk.doc_id)
    if not image_ref_map:
        return []

    existing_by_storage = {
        asset.image_storage_url: asset
        for asset in db.query(ChunkAsset)
        .filter(
            ChunkAsset.chunk_id == chunk.id,
            ChunkAsset.asset_type == "image",
            ChunkAsset.image_storage_url.isnot(None),
        )
        .all()
        if asset.image_storage_url
    }

    ensured: list[ChunkAsset] = []
    base_char = chunk.char_start or 0
    next_id = int(db.query(func.max(ChunkAsset.id)).scalar() or 0)
    for image_ref, rel_start, rel_end in parse_markdown_image_refs(chunk.content):
        storage_path = resolve_image_ref_storage_path(
            db,
            kb_id=chunk.kb_id,
            doc_id=chunk.doc_id,
            image_ref=image_ref,
            image_ref_map=image_ref_map,
        )
        if not storage_path:
            continue

        asset = existing_by_storage.get(storage_path)
        if asset is None:
            next_id += 1
            asset = ChunkAsset(
                id=next_id,
                kb_id=chunk.kb_id,
                doc_id=chunk.doc_id,
                chunk_id=chunk.id,
                asset_type="image",
                char_start=base_char + rel_start,
                char_end=base_char + rel_end,
                raw_markdown=f"![image]({image_ref})",
                image_storage_url=storage_path,
            )
            db.add(asset)
            existing_by_storage[storage_path] = asset
        else:
            asset.chunk_id = chunk.id
            asset.char_start = base_char + rel_start
            asset.char_end = base_char + rel_end
        ensured.append(asset)

    if ensured:
        db.flush()
    return ensured
