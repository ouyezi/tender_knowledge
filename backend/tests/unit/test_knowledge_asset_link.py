from uuid import uuid4

from src.models.chunk_asset import ChunkAsset
from src.services.knowledge.asset_link_service import assets_in_range, link_assets_to_chunk


def test_assets_in_range_requires_asset_fully_inside_section():
    doc_id = uuid4()
    kb_id = uuid4()
    assets = [
        ChunkAsset(kb_id=kb_id, doc_id=doc_id, asset_type="image", char_start=10, char_end=20),
        ChunkAsset(kb_id=kb_id, doc_id=doc_id, asset_type="table", char_start=100, char_end=200),
        ChunkAsset(
            kb_id=kb_id,
            doc_id=doc_id,
            asset_type="table",
            char_start=8,
            char_end=500,
            raw_markdown="| 指标 | 2019 |",
        ),
    ]
    matched = assets_in_range(assets, char_start=5, char_end=25)
    assert len(matched) == 1
    assert matched[0].asset_type == "image"


def test_assets_in_range_filters_by_section_content():
    doc_id = uuid4()
    kb_id = uuid4()
    section = "## 法人代表身份证明\n\n| 法人代表身份证明 | 内容 |"
    assets = [
        ChunkAsset(
            kb_id=kb_id,
            doc_id=doc_id,
            asset_type="table",
            char_start=10,
            char_end=20,
            raw_markdown="| 指标 | 2019 |\n| --- | --- |",
        ),
        ChunkAsset(
            kb_id=kb_id,
            doc_id=doc_id,
            asset_type="table",
            char_start=12,
            char_end=18,
            raw_markdown="| 法人代表身份证明 | 内容 |\n| --- | --- |",
        ),
    ]
    matched = assets_in_range(assets, char_start=5, char_end=25, section_md=section)
    assert len(matched) == 1
    assert "法人代表身份证明" in (matched[0].raw_markdown or "")


def test_assets_in_range_none_bounds_returns_empty():
    doc_id = uuid4()
    kb_id = uuid4()
    assets = [
        ChunkAsset(kb_id=kb_id, doc_id=doc_id, asset_type="image", char_start=10, char_end=20),
    ]
    assert assets_in_range(assets, char_start=None, char_end=20) == []
    assert assets_in_range(assets, char_start=5, char_end=None) == []


def test_link_assets_to_chunk(db_session, seeded_kb):
    doc_id = uuid4()
    kb_id = seeded_kb.kb_id
    chunk_id = 42
    section = "section with image only ![img](images/a.png)"
    overlapping = ChunkAsset(
        id=1,
        kb_id=kb_id,
        doc_id=doc_id,
        asset_type="image",
        char_start=10,
        char_end=20,
        raw_markdown="![img](images/a.png)",
    )
    outside = ChunkAsset(
        id=2,
        kb_id=kb_id,
        doc_id=doc_id,
        asset_type="table",
        char_start=100,
        char_end=200,
        raw_markdown="| far | away |",
    )
    spillover = ChunkAsset(
        id=4,
        kb_id=kb_id,
        doc_id=doc_id,
        asset_type="table",
        char_start=10,
        char_end=200,
        raw_markdown="| spill | over |",
    )
    already_linked = ChunkAsset(
        id=3,
        kb_id=kb_id,
        doc_id=doc_id,
        chunk_id=99,
        asset_type="image",
        char_start=10,
        char_end=20,
    )
    db_session.add_all([overlapping, outside, spillover, already_linked])
    db_session.commit()

    count = link_assets_to_chunk(
        db_session,
        kb_id=kb_id,
        doc_id=doc_id,
        chunk_id=chunk_id,
        char_start=5,
        char_end=25,
        section_md=section,
    )

    assert count == 1
    db_session.refresh(overlapping)
    db_session.refresh(outside)
    db_session.refresh(spillover)
    db_session.refresh(already_linked)
    assert overlapping.chunk_id == chunk_id
    assert outside.chunk_id is None
    assert spillover.chunk_id is None
    assert already_linked.chunk_id == 99
