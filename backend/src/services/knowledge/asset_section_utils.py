from __future__ import annotations

import re

from src.models.chunk_asset import ChunkAsset

_TABLE_REF_COMMENT_RE = re.compile(
    r"<!--\s*table-ref:(?P<ref>tables/t\d{4}\.json)\s*-->"
)


def _normalize_table_markdown(text: str) -> str:
    return "\n".join(line.strip() for line in text.strip().splitlines())


def _table_ref_placeholder_in_section(table_ref: str | None, section_md: str) -> bool:
    if not table_ref:
        return False
    return f"<!-- table-ref:{table_ref} -->" in section_md or f"table-ref:{table_ref}" in section_md


def _table_already_inline_in_section(raw: str, section_md: str) -> bool:
    normalized = _normalize_table_markdown(raw)
    if not normalized:
        return False
    return normalized in section_md


def asset_visible_in_section(asset: ChunkAsset, section_md: str) -> bool:
    if asset.asset_type == "table":
        raw = (asset.raw_markdown or "").strip()
        if not raw:
            return False
        table_schema = asset.table_schema if isinstance(asset.table_schema, dict) else {}
        table_ref = table_schema.get("table_ref")
        if isinstance(table_ref, str) and _table_ref_placeholder_in_section(table_ref, section_md):
            return False
        if _table_already_inline_in_section(raw, section_md):
            return False
        header = raw.split("\n", 1)[0].strip()
        if len(header) >= 3:
            return header in section_md
        return raw in section_md
    if asset.asset_type == "image":
        raw = (asset.raw_markdown or "").strip()
        if raw and raw in section_md:
            return False
        storage_url = (asset.image_storage_url or "").strip()
        if storage_url and storage_url in section_md:
            return False
        filename = storage_url.rsplit("/", 1)[-1] if storage_url else ""
        if filename and filename in section_md:
            return False
        return True
    return True


def _asset_dedupe_key(asset: ChunkAsset) -> tuple:
    if asset.asset_type == "table":
        return (
            asset.asset_type,
            asset.char_start,
            asset.char_end,
            _normalize_table_markdown(asset.raw_markdown or ""),
        )
    if asset.asset_type == "image":
        return (
            asset.asset_type,
            asset.char_start,
            asset.char_end,
            (asset.image_storage_url or "").strip(),
            (asset.raw_markdown or "").strip(),
        )
    return (asset.asset_type, asset.char_start, asset.char_end, asset.id)


def filter_assets_for_section(assets: list[ChunkAsset], section_md: str) -> list[ChunkAsset]:
    if not section_md.strip():
        return []
    seen: set[tuple] = set()
    filtered: list[ChunkAsset] = []
    for asset in assets:
        if not asset_visible_in_section(asset, section_md):
            continue
        key = _asset_dedupe_key(asset)
        if key in seen:
            continue
        seen.add(key)
        filtered.append(asset)
    return filtered


def asset_char_range_within_section(
    asset: ChunkAsset,
    *,
    char_start: int | None,
    char_end: int | None,
) -> bool:
    a0 = asset.char_start
    a1 = asset.char_end
    if a0 is None or a1 is None or char_start is None or char_end is None:
        return False
    if a0 < char_start or a0 >= char_end:
        return False
    return a1 <= char_end
