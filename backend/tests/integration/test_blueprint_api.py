from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus

MOCK_LLM_JSON = """
{
  "title": "供应链方案通用大纲",
  "desc": "供应链模块概要",
  "nodes": [{
    "t": "总体设计",
    "imp": "required",
    "cd": "描述总体设计思路。",
    "tr": "响应评分点。",
    "children": []
  }]
}
""".strip()


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_file_import(db_session, kb_id):
    row = FileImport(
        kb_id=kb_id,
        file_name="blueprint-api.docx",
        file_type=FileType.docx,
        file_size=2048,
        storage_path="/tmp/blueprint-api.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(row)
    db_session.flush()
    return row


def _seed_document_tree(db_session, kb_id):
    file_import = _seed_file_import(db_session, kb_id)
    document = Document(
        kb_id=kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        source_usage=DocumentSourceUsage.knowledge_extract,
        document_name="blueprint-api.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()

    parent_id = uuid4()
    child_id = uuid4()
    parent = DocumentTreeNode(
        node_id=parent_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="第一章 总体方案",
        level=1,
        sort_order=0,
        tree_version=1,
    )
    child = DocumentTreeNode(
        node_id=child_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=parent_id,
        node_type=DocumentTreeNodeType.heading,
        title="1.1 子章节",
        level=2,
        sort_order=1,
        tree_version=1,
    )
    db_session.add_all([parent, child])
    db_session.commit()
    return document, parent, child


def _build_manual_payload(doc_id, node_id, *, name: str, description: str):
    return {
        "name": name,
        "description": description,
        "source_doc_id": str(doc_id),
        "source_node_id": str(node_id),
        "source_chapter_title": "第一章 总体方案",
        "product_tags": ["prod-a"],
        "industry_tags": ["ind-a"],
        "scenario_tags": ["scene-a"],
        "applicable_project_type": ["type-a"],
        "status": "active",
        "nodes": [
            {
                "node_title": "总体设计",
                "node_level": 1,
                "node_order": 1,
                "importance_level": "required",
                "content_description": "写总体设计思路。",
                "tender_response_hint": "响应评分点。",
                "children": [],
            }
        ],
    }


MOCK_LLM_JSON_V11 = """
{
  "title": "供应链方案通用大纲",
  "desc": "供应链模块概要",
  "structure_md": "## 技术模块\\n- 总体设计",
  "nodes": [{
    "t": "总体设计",
    "imp": "required",
    "cd": "写总体设计思路。",
    "tr": "响应评分点。",
    "children": []
  }]
}
""".strip()


def test_generate_create_get_includes_v11_fields(client, db_session, seeded_kb, monkeypatch):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **_: MOCK_LLM_JSON_V11,
    )

    generate_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/generate",
        json={"doc_id": str(document.document_id), "node_id": str(parent.node_id)},
    )
    assert generate_resp.status_code == 200
    draft = generate_resp.json()["data"]
    assert draft["suggested_structure_md"].startswith("## 技术模块")
    assert draft["nodes"][0]["children"][0]["content_description"] == "写总体设计思路。"

    create_resp = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=draft)
    assert create_resp.status_code == 201
    blueprint_id = create_resp.json()["data"]["blueprint_id"]

    detail_resp = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/{blueprint_id}")
    detail = detail_resp.json()["data"]
    assert detail["suggested_structure_md"].startswith("## 技术模块")
    assert detail["nodes"][0]["children"][0]["tender_response_hint"] == "响应评分点。"


def test_generate_create_get_flow(client, db_session, seeded_kb, monkeypatch):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_generate_service._chat_with_timeout",
        lambda **_: MOCK_LLM_JSON,
    )

    generate_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/generate",
        json={
            "doc_id": str(document.document_id),
            "node_id": str(parent.node_id),
        },
    )
    assert generate_resp.status_code == 200
    draft = generate_resp.json()["data"]
    assert draft["name"] == "供应链方案通用大纲"

    create_resp = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=draft)
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    blueprint_id = created["blueprint_id"]

    duplicate_resp = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=draft)
    assert duplicate_resp.status_code == 409
    assert duplicate_resp.json()["error"]["code"] == "blueprint_source_exists"

    detail_resp = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/{blueprint_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["blueprint_id"] == blueprint_id
    assert detail["name"] == "供应链方案通用大纲"
    assert len(detail["nodes"]) == 1


def test_update_blueprint(client, db_session, seeded_kb):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    create_payload = _build_manual_payload(
        document.document_id,
        parent.node_id,
        name="蓝图A",
        description="初版描述",
    )
    create_resp = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=create_payload)
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    assert created["version"] == 1

    update_payload = {
        **create_payload,
        "name": "蓝图A-v2",
        "description": "更新后描述",
    }
    update_resp = client.put(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/{created['blueprint_id']}",
        json=update_payload,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["data"]
    assert updated["name"] == "蓝图A-v2"
    assert updated["version"] == 2


def test_list_and_delete(client, db_session, seeded_kb):
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    payload_1 = _build_manual_payload(
        document.document_id,
        parent.node_id,
        name="网络架构蓝图",
        description="网络设计说明",
    )
    payload_2 = _build_manual_payload(
        document.document_id,
        child.node_id,
        name="服务方案蓝图",
        description="售后服务说明",
    )
    create_1 = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=payload_1)
    create_2 = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=payload_2)
    assert create_1.status_code == 201
    assert create_2.status_code == 201
    created_1 = create_1.json()["data"]

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints",
        params={"keyword": "网络", "page": 1, "page_size": 20},
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()["data"]
    assert list_data["total"] == 1
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["name"] == "网络架构蓝图"

    delete_resp = client.delete(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/{created_1['blueprint_id']}"
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["data"]["deleted"] is True


def test_document_tree_includes_has_blueprint(client, db_session, seeded_kb):
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    create_payload = _build_manual_payload(
        document.document_id,
        parent.node_id,
        name="树节点蓝图",
        description="用于测试 has_blueprint",
    )
    create_resp = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints", json=create_payload)
    assert create_resp.status_code == 201

    tree_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/entry/documents/"
        f"{document.document_id}/tree"
    )
    assert tree_resp.status_code == 200
    tree = tree_resp.json()["data"]["items"]
    assert len(tree) == 1
    assert tree[0]["node_id"] == str(parent.node_id)
    assert tree[0]["has_blueprint"] is True
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["node_id"] == str(child.node_id)
    assert tree[0]["children"][0]["has_blueprint"] is False


MOCK_SUGGEST_JSON = """
{
  "outline_title": "供应链建议目录",
  "summary": "按需求组织章节",
  "nodes": [{
    "title": "总体设计",
    "content_suggestion": "写总体设计思路。",
    "importance": "required",
    "split_reason": null,
    "no_split_reason": "单章覆盖即可。",
    "children": []
  }]
}
""".strip()


def _create_blueprint_for_suggest(client, kb_id, db_session):
    document, parent, _ = _seed_document_tree(db_session, kb_id)
    payload = _build_manual_payload(
        document.document_id,
        parent.node_id,
        name="建议测试蓝图",
        description="用于 suggest-outline",
    )
    create_resp = client.post(f"/api/v1/kbs/{kb_id}/blueprints", json=payload)
    assert create_resp.status_code == 201
    return create_resp.json()["data"]["blueprint_id"]


def test_suggest_outline_happy_path(client, db_session, seeded_kb, monkeypatch):
    blueprint_id = _create_blueprint_for_suggest(client, seeded_kb.kb_id, db_session)
    monkeypatch.setattr(
        "src.services.knowledge.blueprint_outline_suggest_service._chat_with_timeout",
        lambda **_: MOCK_SUGGEST_JSON,
    )
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/suggest-outline",
        json={
            "blueprint_ids": [blueprint_id],
            "requirement_description": "需要突出供应链安全与实施计划",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["outline_title"] == "供应链建议目录"
    assert data["nodes"][0]["no_split_reason"] == "单章覆盖即可。"


def test_suggest_outline_empty_requirement(client, db_session, seeded_kb):
    blueprint_id = _create_blueprint_for_suggest(client, seeded_kb.kb_id, db_session)
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/suggest-outline",
        json={"blueprint_ids": [blueprint_id], "requirement_description": "   "},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_request"


def test_suggest_outline_blueprint_not_found(client, seeded_kb):
    missing_id = str(uuid4())
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/suggest-outline",
        json={
            "blueprint_ids": [missing_id],
            "requirement_description": "测试需求",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "blueprint_not_found"
