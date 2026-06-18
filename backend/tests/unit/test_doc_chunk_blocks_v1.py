from uuid import uuid4

from src.services.doc_chunk.blocks_v1 import chunk_blocks_to_content


def test_chunk_blocks_to_content_paragraph_and_table():
    content = chunk_blocks_to_content(
        [
            {"type": "paragraph", "text": "段落"},
            {"type": "table", "text": "|a|b|"},
        ]
    )
    assert "段落" in content
    assert "|a|b|" in content


def test_chunk_blocks_to_content_unmapped_image_fallback():
    content = chunk_blocks_to_content([{"type": "image", "image_ref": "images/x.png"}])
    assert "[image]" in content


def test_chunk_blocks_to_content_mapped_image():
    asset_id = uuid4()
    content = chunk_blocks_to_content(
        [{"type": "image", "image_ref": "images/x.png"}],
        image_ref_map={"images/x.png": asset_id},
    )
    assert str(asset_id) in content


def test_resolve_image_asset_id_accepts_bare_ref_name():
    from src.services.doc_chunk.blocks_v1 import resolve_image_asset_id

    asset_id = uuid4()
    resolved = resolve_image_asset_id(
        "docx-img-1",
        {"images/docx-img-1.png": asset_id},
    )
    assert resolved == asset_id
