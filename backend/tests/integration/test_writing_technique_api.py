from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.knowledge_chunk import KnowledgeChunk


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_chunk(db_session, kb_id, *, chunk_id: int, title: str = "项目理解"):
    row = KnowledgeChunk(
        id=chunk_id,
        kb_id=kb_id,
        knowledge_code=f"K-{chunk_id}",
        version="1.0",
        title=title,
        content="建设背景与目标，实施路径与质量保障。",
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


def _create_payload(*, title: str, source_chunk_id: int | None = None):
    payload = {
        "title": title,
        "applicable_scene": "适用于项目理解章节",
        "writing_summary": "先背景后目标",
        "applicable_sections": ["项目理解"],
        "tags": ["技术方案"],
        "usage_mode": "DIRECT",
        "recommended_outline": "项目理解\n- 建设背景",
        "writing_strategy": "突出针对性",
        "must_include": "建设背景与目标",
        "notes": "",
        "output_requirement": "三级标题",
        "checklist": "是否响应招标要求",
        "confidence": 80,
        "source_chunk_id": source_chunk_id,
    }
    return payload


def test_generate_creates_draft(client, db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=701)
    monkeypatch.setattr(
        "src.services.knowledge.writing_technique_generate_service._chat_with_timeout",
        lambda **_: json.dumps({"title": "自动生成技巧", "usage_mode": "DIRECT", "score": 88}, ensure_ascii=False),
    )

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques/generate",
        json={"chunk_id": chunk.id},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "自动生成技巧"
    assert data["status"] == "draft"
    assert data["source_chunk_id"] == chunk.id
    assert data["confidence"] == 88


def test_generate_conflict_without_confirm(client, db_session, seeded_kb, monkeypatch):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=702)
    first_create = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques",
        json=_create_payload(title="已存在技巧", source_chunk_id=chunk.id),
    )
    assert first_create.status_code == 201
    monkeypatch.setattr(
        "src.services.knowledge.writing_technique_generate_service._chat_with_timeout",
        lambda **_: json.dumps({"title": "冲突测试", "usage_mode": "REFERENCE", "score": 77}, ensure_ascii=False),
    )

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques/generate",
        json={"chunk_id": chunk.id, "confirm_overwrite": False},
    )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "technique_exists"


def test_bind_source_conflict(client, db_session, seeded_kb):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=703)

    owner_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques",
        json=_create_payload(title="技巧A", source_chunk_id=chunk.id),
    )
    assert owner_resp.status_code == 201

    other_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques",
        json=_create_payload(title="技巧B"),
    )
    assert other_resp.status_code == 201
    other_id = other_resp.json()["data"]["technique_id"]

    bind_resp = client.put(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques/{other_id}/bind-source",
        json={"chunk_id": chunk.id},
    )

    assert bind_resp.status_code == 409
    assert bind_resp.json()["error"]["code"] == "chunk_already_bound"


def test_get_by_source(client, db_session, seeded_kb):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=704)
    create_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques",
        json=_create_payload(title="按来源查询", source_chunk_id=chunk.id),
    )
    assert create_resp.status_code == 201
    created_id = create_resp.json()["data"]["technique_id"]

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques/by-source",
        params={"chunk_id": chunk.id},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data is not None
    assert data["technique_id"] == created_id
    assert data["source_chunk_id"] == chunk.id
