from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.chunk_asset import ChunkAsset
from src.services.knowledge.asset_section_utils import (
    asset_char_range_within_section,
    filter_assets_for_section,
)


def assets_in_range(
    assets: list[ChunkAsset],
    *,
    char_start: int | None,
    char_end: int | None,
    section_md: str | None = None,
) -> list[ChunkAsset]:
    if char_start is None or char_end is None:
        return []
    result: list[ChunkAsset] = []
    for asset in assets:
        if not asset_char_range_within_section(
            asset,
            char_start=char_start,
            char_end=char_end,
        ):
            continue
        result.append(asset)
    if section_md is not None:
        return filter_assets_for_section(result, section_md)
    return result


def link_assets_to_chunk(
    db: Session,
    *,
    kb_id,
    doc_id,
    chunk_id: int,
    char_start: int | None,
    char_end: int | None,
    section_md: str | None = None,
) -> int:
    rows = (
        db.query(ChunkAsset)
        .filter(
            ChunkAsset.kb_id == kb_id,
            ChunkAsset.doc_id == doc_id,
            ChunkAsset.chunk_id.is_(None),
        )
        .all()
    )
    matched = assets_in_range(
        rows,
        char_start=char_start,
        char_end=char_end,
        section_md=section_md,
    )
    for row in matched:
        row.chunk_id = chunk_id
    db.flush()
    return len(matched)
