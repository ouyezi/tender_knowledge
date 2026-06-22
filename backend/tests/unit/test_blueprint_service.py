from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.services.knowledge.blueprint_service import (
    BlueprintConflictError,
    BlueprintValidationError,
    create_blueprint,
    delete_blueprints_by_doc_id,
    get_blueprint_by_source,
    get_blueprint_detail,
    update_blueprint,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _nodes(level1_title: str = "章节一") -> list[dict]:
    return [
        {
            "node_title": level1_title,
            "node_level": 1,
            "node_order": 1,
            "importance_level": "required",
            "children": [
                {
                    "node_title": "子章节 1.1",
                    "node_level": 2,
                    "node_order": 1,
                    "importance_level": "recommended",
                    "children": [],
                }
            ],
        }
    ]


def _payload(source_doc_id=None, source_node_id=None, *, name: str = "蓝图A") -> dict:
    return {
        "name": name,
        "description": "测试蓝图",
        "source_doc_id": source_doc_id or uuid4(),
        "source_node_id": source_node_id or uuid4(),
        "source_chapter_title": "第一章",
        "product_tags": ["prod-a"],
        "industry_tags": ["ind-a"],
        "scenario_tags": ["scene-a"],
        "applicable_project_type": ["type-a"],
        "status": "active",
        "nodes": _nodes(),
    }


def test_create_and_get_by_source(db_session, seeded_kb):
    source_node_id = uuid4()
    blueprint = create_blueprint(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=_payload(source_node_id=source_node_id),
    )
    db_session.commit()

    got = get_blueprint_by_source(
        db_session,
        kb_id=seeded_kb.kb_id,
        source_node_id=source_node_id,
    )
    assert got is not None
    assert got.blueprint_id == blueprint.blueprint_id
    assert got.name == "蓝图A"


def test_create_duplicate_source_raises_blueprint_conflict_error(db_session, seeded_kb):
    source_node_id = uuid4()
    create_blueprint(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=_payload(source_node_id=source_node_id),
    )
    db_session.commit()

    with pytest.raises(BlueprintConflictError):
        create_blueprint(
            db_session,
            kb_id=seeded_kb.kb_id,
            payload=_payload(source_node_id=source_node_id),
        )


def test_update_increments_version(db_session, seeded_kb):
    source_node_id = uuid4()
    blueprint = create_blueprint(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=_payload(source_node_id=source_node_id),
    )
    db_session.commit()

    updated = update_blueprint(
        db_session,
        kb_id=seeded_kb.kb_id,
        blueprint_id=blueprint.blueprint_id,
        payload={
            **_payload(source_doc_id=blueprint.source_doc_id, source_node_id=source_node_id),
            "name": "蓝图A-v2",
        },
    )
    db_session.commit()

    assert updated.version == 2
    assert updated.name == "蓝图A-v2"


def test_validation_empty_name(db_session, seeded_kb):
    with pytest.raises(BlueprintValidationError):
        create_blueprint(
            db_session,
            kb_id=seeded_kb.kb_id,
            payload=_payload(name=""),
        )


def test_validation_no_level1_nodes(db_session, seeded_kb):
    payload = _payload()
    payload["nodes"] = [
        {
            "node_title": "非法根节点",
            "node_level": 2,
            "node_order": 1,
            "importance_level": "required",
            "children": [],
        }
    ]
    with pytest.raises(BlueprintValidationError):
        create_blueprint(db_session, kb_id=seeded_kb.kb_id, payload=payload)


def test_delete_blueprints_by_doc_id(db_session, seeded_kb):
    doc_a = uuid4()
    doc_b = uuid4()
    create_blueprint(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=_payload(source_doc_id=doc_a, source_node_id=uuid4(), name="蓝图1"),
    )
    create_blueprint(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=_payload(source_doc_id=doc_a, source_node_id=uuid4(), name="蓝图2"),
    )
    keep = create_blueprint(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=_payload(source_doc_id=doc_b, source_node_id=uuid4(), name="蓝图3"),
    )
    db_session.commit()

    deleted = delete_blueprints_by_doc_id(db_session, doc_id=doc_a)
    db_session.commit()

    assert deleted == 2
    assert db_session.get(type(keep), keep.blueprint_id) is not None


def test_create_persists_generation_extraction_fields(db_session, seeded_kb):
    payload = _payload()
    payload["suggested_structure_md"] = "## 模块\n- 技术方案"
    payload["nodes"] = [
        {
            "node_title": "章节一",
            "node_level": 1,
            "node_order": 1,
            "importance_level": "required",
            "content_description": "写架构设计。",
            "tender_response_hint": "响应星号条款。",
            "children": [],
        }
    ]
    blueprint = create_blueprint(db_session, kb_id=seeded_kb.kb_id, payload=payload)
    db_session.commit()

    detail = get_blueprint_detail(
        db_session,
        kb_id=seeded_kb.kb_id,
        blueprint_id=blueprint.blueprint_id,
    )
    assert detail["suggested_structure_md"] == "## 模块\n- 技术方案"
    assert detail["nodes"][0]["content_description"] == "写架构设计。"
    assert detail["nodes"][0]["tender_response_hint"] == "响应星号条款。"
