import hashlib

from src.services.knowledge.chunk_index_text import (
    build_chunk_highlights,
    build_index_content_hash,
    chunk_keyword_score,
)


def test_build_index_content_hash():
    digest = build_index_content_hash(title="标题", summary="摘要", content="正文")
    assert len(digest) == 64


def test_chunk_keyword_score_title_weighted():
    score = chunk_keyword_score(
        keyword="ISO9001 证书",
        title="ISO9001质量管理体系证书",
        summary="",
        content="",
        title_weight=3.0,
        body_weight=1.0,
    )
    assert score > 0.5


def test_build_chunk_highlights():
    items = build_chunk_highlights(
        keyword="资质",
        title="企业资质",
        summary="含多项资质证书",
        content="",
    )
    assert items
    assert "<em>" in items[0]["snippet"]
