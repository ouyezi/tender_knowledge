from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.knowledge_chunk import KnowledgeChunk
from src.models.writing_technique import TechniqueStatus, WritingTechnique
from src.services.knowledge.writing_technique_service import (
    TechniqueChunkBoundError,
    bind_source_chunk,
    create_technique,
    invalidate_techniques_by_chunk_ids,
    publish_technique,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_chunk(db_session, kb_id, *, chunk_id=101):
    row = KnowledgeChunk(
        id=chunk_id,
        kb_id=kb_id,
        knowledge_code=f"K-{chunk_id}",
        version="1.0",
        title="项目理解章节",
        content="建设背景与目标...",
        knowledge_type="method",
        doc_id=uuid4(),
        source_type="bid",
        catalog_path=[],
        primary_node_id=str(uuid4()),
        block_type_code="product_solution",
        application_type_code="preferred_reference",
        business_line_codes=["general"],
        tags=[],
        industries=[],
        customer_types=[],
        regions=[],
        content_hash=f"hash-{chunk_id}",
        token_count=10,
        is_latest=True,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_create_technique_without_source(db_session, seeded_kb):
    row = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "服务方案写作技巧", "usage_mode": "DIRECT"},
    )
    db_session.commit()

    assert row.title == "服务方案写作技巧"
    assert row.source_chunk_id is None
    assert row.status == TechniqueStatus.draft


def test_bind_source_chunk_conflict(db_session, seeded_kb):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "A", "source_chunk_id": chunk.id},
    )
    db_session.commit()

    other = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "B"},
    )
    db_session.commit()

    with pytest.raises(TechniqueChunkBoundError):
        bind_source_chunk(
            db_session,
            kb_id=seeded_kb.kb_id,
            technique_id=other.technique_id,
            chunk_id=chunk.id,
        )


def test_publish_increments_version(db_session, seeded_kb):
    row = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "发布测试", "usage_mode": "REFERENCE"},
    )
    db_session.commit()

    published = publish_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        technique_id=row.technique_id,
    )
    db_session.commit()

    assert published.status == TechniqueStatus.published
    assert published.version == 2


def test_invalidate_techniques_by_chunk_ids(db_session, seeded_kb):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=202)
    row = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "待失效", "source_chunk_id": chunk.id},
    )
    db_session.commit()

    count = invalidate_techniques_by_chunk_ids(
        db_session,
        kb_id=seeded_kb.kb_id,
        chunk_ids=[chunk.id],
    )
    db_session.commit()
    refreshed = db_session.get(WritingTechnique, row.technique_id)

    assert count == 1
    assert refreshed is not None
    assert refreshed.source_chunk_id is None
    assert refreshed.source_invalid is True
