from uuid import uuid4

from src.models.document_media_asset import DocumentMediaAsset
from src.services.knowledge.media_url_service import (
    load_image_ref_map_payload,
    resolve_image_ref_to_media_url,
    resolve_storage_path_to_media_url,
)


def test_resolve_storage_path_to_media_url(db_session, seeded_kb):
    doc_id = uuid4()
    asset_id = uuid4()
    storage_path = f"{seeded_kb.kb_id}/media/{doc_id}/img.png"
    db_session.add(
        DocumentMediaAsset(
            asset_id=asset_id,
            kb_id=seeded_kb.kb_id,
            document_id=doc_id,
            storage_path=storage_path,
            mime_type="image/png",
        )
    )
    db_session.flush()

    url = resolve_storage_path_to_media_url(
        db_session,
        kb_id=seeded_kb.kb_id,
        storage_path=storage_path,
    )
    assert url == f"/api/v1/kbs/{seeded_kb.kb_id}/media/{asset_id}"


def test_resolve_image_ref_to_media_url():
    asset_id = uuid4()
    image_ref_map = {"images/docx-img-005.jpeg": str(asset_id)}
    kb_id = uuid4()

    url = resolve_image_ref_to_media_url(
        kb_id=kb_id,
        image_ref="docx-img-005.jpeg",
        image_ref_map=image_ref_map,
    )
    assert url == f"/api/v1/kbs/{kb_id}/media/{asset_id}"


def test_load_image_ref_map_payload_empty(tmp_path, monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings, "storage_root", str(tmp_path))
    assert load_image_ref_map_payload(document_id=uuid4()) == {}
