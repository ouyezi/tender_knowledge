from uuid import uuid4

from src.models.document_media_asset import DocumentMediaAsset


def test_create_document_media_asset(db_session, seeded_kb):
    document_id = uuid4()
    row = DocumentMediaAsset(
        kb_id=seeded_kb.kb_id,
        document_id=document_id,
        storage_path=f"{seeded_kb.kb_id}/media/{document_id}/img.png",
        mime_type="image/png",
        source_block_index=3,
    )
    db_session.add(row)
    db_session.commit()
    assert row.asset_id is not None
