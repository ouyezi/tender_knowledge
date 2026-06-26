from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.knowledge_chunk import KnowledgeChunk
from src.models.writing_technique import TechniqueStatus
from src.services.knowledge.writing_technique_generate_service import (
    generate_and_save_technique,
    parse_llm_technique_payload,
)
from src.services.knowledge.writing_technique_service import (
    TechniqueConflictError,
    create_technique,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_chunk(db_session, kb_id, *, chunk_id=303):
    row = KnowledgeChunk(
        id=chunk_id,
        kb_id=kb_id,
        knowledge_code=f"K-{chunk_id}",
        version="1.0",
        title="项目理解章节",
        content="建设背景与目标，实施路径与质量保障。",
        knowledge_type="method",
        doc_id=uuid4(),
        source_type="bid",
        catalog_path=[],
        primary_node_id=str(uuid4()),
        category="technical",
        tags=[],
        products=[],
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


def test_parse_llm_technique_payload_maps_score_to_confidence():
    raw = {
        "title": "项目理解写作蓝图",
        "applicable_scene": "适用于项目理解章节",
        "writing_summary": "先背景后目标",
        "applicable_sections": ["项目理解"],
        "tags": ["项目理解", "技术方案"],
        "usage_mode": "DIRECT",
        "recommended_outline": "项目理解\n- 建设背景",
        "writing_strategy": "突出针对性",
        "must_include": "建设背景与目标",
        "notes": "",
        "output_requirement": "三级标题",
        "checklist": "是否响应招标要求",
        "score": 95,
    }

    parsed = parse_llm_technique_payload(json.dumps(raw, ensure_ascii=False))

    assert parsed["title"] == "项目理解写作蓝图"
    assert parsed["confidence"] == 95
    assert parsed["usage_mode"] == "DIRECT"


def test_parse_llm_technique_payload_fallback_usage_mode():
    parsed = parse_llm_technique_payload(
        json.dumps({"title": "x", "usage_mode": "BAD", "score": 200})
    )
    assert parsed["usage_mode"] == "REFERENCE"
    assert parsed["confidence"] == 100


def test_generate_and_save_technique_creates_draft(db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=303)
    monkeypatch.setattr(
        "src.services.knowledge.writing_technique_generate_service._chat_with_timeout",
        lambda **kwargs: json.dumps(
            {"title": "测试", "usage_mode": "DIRECT", "score": 80},
            ensure_ascii=False,
        ),
    )

    row = generate_and_save_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        chunk_id=chunk.id,
        confirm_overwrite=False,
    )
    db_session.commit()

    assert row.source_chunk_id == chunk.id
    assert row.status.value == "draft"
    assert row.confidence == 80


def test_generate_and_save_technique_confirm_overwrite_existing(
    db_session, seeded_kb, monkeypatch
):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=404)
    existing = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "已有技巧", "source_chunk_id": chunk.id},
    )
    existing.status = TechniqueStatus.published
    existing.version = 3
    db_session.commit()

    with pytest.raises(TechniqueConflictError):
        generate_and_save_technique(
            db_session,
            kb_id=seeded_kb.kb_id,
            chunk_id=chunk.id,
            confirm_overwrite=False,
        )

    monkeypatch.setattr(
        "src.services.knowledge.writing_technique_generate_service._chat_with_timeout",
        lambda **kwargs: json.dumps(
            {"title": "覆盖后", "usage_mode": "EXTRACT", "score": 66},
            ensure_ascii=False,
        ),
    )

    updated = generate_and_save_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        chunk_id=chunk.id,
        confirm_overwrite=True,
    )
    db_session.commit()

    assert updated.technique_id == existing.technique_id
    assert updated.title == "覆盖后"
    assert updated.status == TechniqueStatus.draft
    assert updated.version == 4
    assert updated.confidence == 66
