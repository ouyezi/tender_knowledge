from pathlib import Path
from uuid import uuid4

from src.config import Settings
from src.models.document_media_asset import DocumentMediaAsset


def test_get_media_asset_returns_image(client, db_session, seeded_kb):
    document_id = uuid4()
    rel = f"{seeded_kb.kb_id}/media/{document_id}/test.png"
    abs_path = Path(Settings().storage_root) / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    row = DocumentMediaAsset(
        kb_id=seeded_kb.kb_id,
        document_id=document_id,
        storage_path=rel,
        mime_type="image/png",
    )
    db_session.add(row)
    db_session.commit()

    resp = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/media/{row.asset_id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")


def test_get_media_asset_wrong_kb_returns_404(client, db_session, seeded_kb):
    other_kb = uuid4()
    row = DocumentMediaAsset(
        kb_id=other_kb,
        document_id=uuid4(),
        storage_path="x/y/z.png",
        mime_type="image/png",
    )
    db_session.add(row)
    db_session.commit()
    resp = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/media/{row.asset_id}")
    assert resp.status_code == 404
