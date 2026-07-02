from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import Settings
from src.models.chunk_asset import ChunkAsset
from src.models.document_media_asset import DocumentMediaAsset
from src.services.doc_chunk.blocks_v1 import resolve_image_asset_id


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _position_from_item(item: dict[str, Any]) -> tuple[int | None, int | None]:
    anchor = item.get("anchor")
    if not isinstance(anchor, dict):
        anchor = {}
    char_start = item.get("char_start")
    char_end = item.get("char_end")
    if char_start is None:
        char_start = anchor.get("char_start")
    if char_end is None:
        char_end = anchor.get("char_end")
    if not isinstance(char_start, int) or not isinstance(char_end, int):
        return (None, None)
    return (char_start, char_end)


def _chunk_fallback_range(chunk_payload: dict[str, Any]) -> tuple[int | None, int | None]:
    source_ranges = chunk_payload.get("source_ranges")
    if not isinstance(source_ranges, list):
        return (None, None)
    for item in source_ranges:
        if not isinstance(item, dict):
            continue
        char_start = item.get("char_start")
        char_end = item.get("char_end")
        if isinstance(char_start, int) and isinstance(char_end, int):
            return (char_start, char_end)
    return (None, None)


def _locate_markdown_in_content(
    content_md: str,
    markdown: str,
    *,
    search_from: int = 0,
) -> tuple[int, int] | None:
    snippet = markdown.strip()
    if not snippet or not content_md:
        return None

    idx = content_md.find(snippet, search_from)
    if idx >= 0:
        return (idx, idx + len(snippet))

    first_line = snippet.split("\n", 1)[0].strip()
    if len(first_line) < 3:
        return None
    idx = content_md.find(first_line, search_from)
    if idx < 0:
        return None
    end = min(idx + len(snippet), len(content_md))
    return (idx, end)


def _load_blocks_table_refs(workspace: Path) -> dict[int, str]:
    payload = _load_json(workspace / "content.blocks.json") or {}
    mapping: dict[int, str] = {}
    for block in payload.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        table_ref = block.get("table_ref")
        block_index = block.get("block_index")
        if table_ref and isinstance(block_index, int):
            mapping[block_index] = str(table_ref)
    return mapping


def _load_tables_manifest(workspace: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(workspace / "tables" / "manifest.json") or {}
    by_ref: dict[str, dict[str, Any]] = {}
    for entry in payload.get("tables") or []:
        if not isinstance(entry, dict):
            continue
        table_ref = str(entry.get("table_ref") or "").strip()
        if table_ref:
            by_ref[table_ref] = entry
    return by_ref


def _load_table_sidecar(workspace: Path, table_ref: str) -> dict[str, Any] | None:
    return _load_json(workspace / table_ref)


def _table_markdown_for_block(
    block: dict[str, Any],
    *,
    workspace: Path,
    blocks_table_refs: dict[int, str],
) -> str:
    markdown = str(block.get("text") or block.get("markdown") or "").strip()
    table_ref = block.get("table_ref")
    if not table_ref:
        block_index = block.get("block_index")
        if isinstance(block_index, int):
            table_ref = blocks_table_refs.get(block_index)
    sidecar = _load_table_sidecar(workspace, str(table_ref)) if table_ref else None
    if sidecar:
        return str(sidecar.get("markdown") or markdown).strip()
    return markdown


def _resolve_table_ref(
    block: dict[str, Any],
    *,
    blocks_table_refs: dict[int, str],
) -> str | None:
    table_ref = block.get("table_ref")
    if table_ref:
        return str(table_ref)
    block_index = block.get("block_index")
    if isinstance(block_index, int):
        return blocks_table_refs.get(block_index)
    return None


def _table_asset_fields(
    sidecar: dict[str, Any] | None,
    *,
    table_ref: str | None,
) -> dict[str, Any]:
    if not sidecar:
        return {}
    logical_rows = sidecar.get("logical_rows") or []
    headers = logical_rows[0] if logical_rows else None
    body_rows = logical_rows[1:] if len(logical_rows) > 1 else []
    return {
        "raw_markdown": sidecar.get("markdown"),
        "table_summary": sidecar.get("llm_text"),
        "table_schema": {
            "schema_version": sidecar.get("schema_version"),
            "layout_type": sidecar.get("layout_type"),
            "grid_width": sidecar.get("grid_width"),
            "record_groups": sidecar.get("record_groups") or [],
            "table_ref": table_ref,
            "slice_ref": sidecar.get("slice_ref"),
            "slice_status": sidecar.get("slice_status"),
        },
        "table_headers": headers,
        "table_rows": body_rows,
    }


def _copy_table_slice_to_storage(
    *,
    workspace: Path,
    sidecar: dict[str, Any],
    kb_id: UUID,
    doc_id: UUID,
    asset_id: int,
) -> str | None:
    if sidecar.get("slice_status") != "ok":
        return None
    slice_ref = str(sidecar.get("slice_ref") or "").strip()
    if not slice_ref:
        return None
    source_path = workspace / slice_ref
    if not source_path.is_file():
        return None

    storage_root = Path(Settings().storage_root)
    rel_path = Path(str(kb_id)) / "media" / str(doc_id) / "tables" / f"{asset_id}.docx"
    dest = storage_root / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest)
    return str(rel_path).replace("\\", "/")


def _lookup_image_storage(
    db: Session,
    *,
    kb_id: UUID,
    doc_id: UUID,
    entry: dict[str, Any],
    image_ref_map: dict[str, UUID],
    cache: dict[UUID, str | None],
) -> str | None:
    image_ref = str(entry.get("image_ref") or "").strip()
    asset_id = resolve_image_asset_id(image_ref, image_ref_map) if image_ref else None
    if asset_id is None:
        return None

    if asset_id in cache:
        return cache[asset_id]

    row = (
        db.query(DocumentMediaAsset.storage_path)
        .filter(
            DocumentMediaAsset.asset_id == asset_id,
            DocumentMediaAsset.kb_id == kb_id,
            DocumentMediaAsset.document_id == doc_id,
        )
        .one_or_none()
    )
    storage_path = row[0] if row else None
    cache[asset_id] = storage_path
    return storage_path


def seed_chunk_assets_from_workspace(
    db: Session,
    *,
    kb_id: UUID,
    doc_id: UUID,
    workspace_path: Path,
    image_ref_map: dict[str, UUID] | None = None,
) -> int:
    created = 0
    workspace = Path(workspace_path)
    image_ref_map = image_ref_map or {}
    media_storage_cache: dict[UUID, str | None] = {}
    blocks_table_refs = _load_blocks_table_refs(workspace)
    tables_manifest = _load_tables_manifest(workspace)
    next_id = db.query(func.max(ChunkAsset.id)).scalar() or 0
    content_md_path = workspace / "content.md"
    content_md = (
        content_md_path.read_text(encoding="utf-8")
        if content_md_path.is_file()
        else ""
    )
    content_search_cursor = 0

    images_manifest = _load_json(workspace / "images" / "manifest.json") or {}
    for entry in images_manifest.get("images") or []:
        if not isinstance(entry, dict):
            continue
        char_start, char_end = _position_from_item(entry)
        if char_start is None or char_end is None:
            continue
        next_id += 1
        db.add(
            ChunkAsset(
                id=next_id,
                kb_id=kb_id,
                doc_id=doc_id,
                chunk_id=None,
                asset_type="image",
                char_start=char_start,
                char_end=char_end,
                image_storage_url=_lookup_image_storage(
                    db,
                    kb_id=kb_id,
                    doc_id=doc_id,
                    entry=entry,
                    image_ref_map=image_ref_map,
                    cache=media_storage_cache,
                ),
            )
        )
        created += 1

    chunks_dir = workspace / "chunks"
    for chunk_path in sorted(chunks_dir.glob("chunk-*.json")):
        chunk_payload = _load_json(chunk_path)
        if not chunk_payload:
            continue
        fallback_start, fallback_end = _chunk_fallback_range(chunk_payload)
        for block in chunk_payload.get("blocks") or []:
            if not isinstance(block, dict) or block.get("type") != "table":
                continue
            table_ref = _resolve_table_ref(block, blocks_table_refs=blocks_table_refs)
            manifest_entry = tables_manifest.get(table_ref) if table_ref else None
            char_start, char_end = _position_from_item(block)
            if (char_start is None or char_end is None) and manifest_entry:
                char_start, char_end = _position_from_item(manifest_entry)
            markdown = _table_markdown_for_block(
                block,
                workspace=workspace,
                blocks_table_refs=blocks_table_refs,
            )
            if char_start is None or char_end is None:
                located = (
                    _locate_markdown_in_content(
                        content_md,
                        markdown,
                        search_from=content_search_cursor,
                    )
                    if content_md and markdown
                    else None
                )
                if located is not None:
                    char_start, char_end = located
                    content_search_cursor = char_end
                else:
                    char_start, char_end = fallback_start, fallback_end
            if char_start is None or char_end is None:
                continue
            sidecar = _load_table_sidecar(workspace, str(table_ref)) if table_ref else None
            fields = (
                _table_asset_fields(sidecar, table_ref=table_ref)
                if sidecar
                else {"raw_markdown": markdown or None}
            )
            next_id += 1
            table_storage_url = None
            if sidecar:
                table_storage_url = _copy_table_slice_to_storage(
                    workspace=workspace,
                    sidecar=sidecar,
                    kb_id=kb_id,
                    doc_id=doc_id,
                    asset_id=next_id,
                )
            db.add(
                ChunkAsset(
                    id=next_id,
                    kb_id=kb_id,
                    doc_id=doc_id,
                    chunk_id=None,
                    asset_type="table",
                    char_start=char_start,
                    char_end=char_end,
                    table_storage_url=table_storage_url,
                    **fields,
                )
            )
            created += 1

    db.flush()
    return created
