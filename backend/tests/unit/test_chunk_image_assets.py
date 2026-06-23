from uuid import uuid4

from src.models.chunk_asset import ChunkAsset
from src.models.document_media_asset import DocumentMediaAsset
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.doc_chunk.content_md_store import persist_image_ref_map
from src.services.knowledge.chunk_image_assets import (
    ensure_image_assets_for_chunk,
    parse_markdown_image_refs,
)


def test_parse_markdown_image_refs():
    content = "## 标题\n\n![docx-img-006](images/docx-img-006.jpeg)\n"
    refs = parse_markdown_image_refs(content)
    assert refs == [("images/docx-img-006.jpeg", content.index("!"), content.index(")") + 1)]


def test_ensure_image_assets_for_chunk_creates_image_asset(db_session, seeded_kb, tmp_path, monkeypatch):
    from src.config import settings

    monkeypatch.setattr(settings, "storage_root", str(tmp_path))

    doc_id = uuid4()
    asset_id = uuid4()
    storage_path = f"{seeded_kb.kb_id}/media/{doc_id}/img.jpg"
    db_session.add(
        DocumentMediaAsset(
            asset_id=asset_id,
            kb_id=seeded_kb.kb_id,
            document_id=doc_id,
            storage_path=storage_path,
            mime_type="image/jpeg",
        )
    )
    persist_image_ref_map(
        document_id=doc_id,
        image_ref_map={"images/docx-img-006.jpeg": asset_id},
        storage_root=tmp_path,
    )

    chunk = KnowledgeChunk(
        kb_id=seeded_kb.kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        title="食品经营许可证",
        content="## 食品经营许可证\n\n![docx-img-006](images/docx-img-006.jpeg)\n",
        knowledge_type="fact",
        content_type="text",
        doc_id=doc_id,
        source_type="bid",
        primary_node_id=str(uuid4()),
        quote_mode="full",
        category="technical",
        status="active",
        char_start=100,
        char_end=180,
    )
    db_session.add(chunk)
    db_session.flush()

    assets = ensure_image_assets_for_chunk(db_session, chunk)
    assert len(assets) == 1
    assert assets[0].asset_type == "image"
    assert assets[0].chunk_id == chunk.id
    assert assets[0].image_storage_url == storage_path
    assert assets[0].char_start == 100 + chunk.content.index("!")
    assert db_session.query(ChunkAsset).filter(ChunkAsset.asset_type == "image").count() == 1
