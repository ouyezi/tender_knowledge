from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.chunk_asset import ChunkAsset


def assets_in_range(
    assets: list[ChunkAsset],
    *,
    char_start: int | None,
    char_end: int | None,
) -> list[ChunkAsset]:
    if char_start is None or char_end is None:
        return []
    result: list[ChunkAsset] = []
    for asset in assets:
        a0 = asset.char_start
        a1 = asset.char_end
        if a0 is None or a1 is None:
            continue
        if a0 < char_end and a1 > char_start:
            result.append(asset)
    return result


def link_assets_to_chunk(
    db: Session,
    *,
    kb_id,
    doc_id,
    chunk_id: int,
    char_start: int | None,
    char_end: int | None,
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
    matched = assets_in_range(rows, char_start=char_start, char_end=char_end)
    for row in matched:
        row.chunk_id = chunk_id
    db.flush()
    return len(matched)
