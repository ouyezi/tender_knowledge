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
        application_type_code="preferred_reference",
        block_type_code="product_solution",
        business_line_codes=["general"],
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


def test_ensure_image_assets_for_chunk_creates_distinct_ids_for_multiple_images(
    db_session, seeded_kb, tmp_path, monkeypatch
):
    from src.config import settings

    monkeypatch.setattr(settings, "storage_root", str(tmp_path))

    doc_id = uuid4()
    asset_ids = [uuid4(), uuid4()]
    storage_paths = [f"{seeded_kb.kb_id}/media/{doc_id}/img-{i}.jpg" for i in range(2)]
    for asset_id, storage_path in zip(asset_ids, storage_paths, strict=True):
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
        image_ref_map={
            "images/docx-img-007.jpeg": asset_ids[0],
            "images/docx-img-008.jpeg": asset_ids[1],
        },
        storage_root=tmp_path,
    )

    chunk = KnowledgeChunk(
        kb_id=seeded_kb.kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        title="ICP电信增值业务许可证",
        content=(
            "## ICP电信增值业务许可证\n\n"
            "![docx-img-007](images/docx-img-007.jpeg)\n\n"
            "![docx-img-008](images/docx-img-008.jpeg)\n"
        ),
        knowledge_type="fact",
        content_type="text",
        doc_id=doc_id,
        source_type="bid",
        primary_node_id=str(uuid4()),
        application_type_code="preferred_reference",
        block_type_code="product_solution",
        business_line_codes=["general"],
        status="active",
        char_start=7044,
        char_end=7147,
    )
    db_session.add(chunk)
    db_session.flush()

    assets = ensure_image_assets_for_chunk(db_session, chunk)
    db_session.commit()

    assert len(assets) == 2
    assert assets[0].id != assets[1].id
    assert {asset.image_storage_url for asset in assets} == set(storage_paths)
