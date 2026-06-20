from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.document_media_asset import DocumentMediaAsset
from src.services.doc_chunk.blocks_v1 import resolve_image_asset_id
from src.services.doc_chunk.content_md_store import load_image_ref_map


def build_media_api_url(*, kb_id: UUID, asset_id: UUID) -> str:
    return f"/api/v1/kbs/{kb_id}/media/{asset_id}"


def resolve_storage_path_to_media_url(
    db: Session,
    *,
    kb_id: UUID,
    storage_path: str | None,
) -> str | None:
    if not storage_path:
        return None
    if storage_path.startswith("/api/") or storage_path.startswith("http://") or storage_path.startswith("https://"):
        return storage_path
    row = (
        db.query(DocumentMediaAsset.asset_id)
        .filter(
            DocumentMediaAsset.kb_id == kb_id,
            DocumentMediaAsset.storage_path == storage_path,
        )
        .one_or_none()
    )
    if row is None:
        return None
    return build_media_api_url(kb_id=kb_id, asset_id=row[0])


def load_image_ref_map_payload(*, document_id: UUID) -> dict[str, str]:
    return {key: str(value) for key, value in load_image_ref_map(document_id=document_id).items()}


def resolve_image_ref_to_media_url(
    *,
    kb_id: UUID,
    image_ref: str,
    image_ref_map: dict[str, UUID] | dict[str, str],
) -> str | None:
    normalized_map: dict[str, UUID] = {}
    for key, value in image_ref_map.items():
        try:
            normalized_map[str(key)] = UUID(str(value))
        except ValueError:
            continue
    asset_id = resolve_image_asset_id(image_ref, normalized_map)
    if asset_id is None:
        return None
    return build_media_api_url(kb_id=kb_id, asset_id=asset_id)
