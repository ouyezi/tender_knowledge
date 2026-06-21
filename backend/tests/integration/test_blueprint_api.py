from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus

MOCK_LLM_JSON = """
{
  "outline_title": "供应链方案通用大纲",
  "overall_strategy": "强调仓配能力",
  "usual_page_range": "5-8页",
  "related_regulations": ["ISO9001"],
  "common_mistakes": "忽视应急预案",
  "template_style": "formal",
  "nodes": [{
    "node_title": "总体设计", "node_level": 1, "children": [],
    "purpose": "p", "writing_goal": "g", "writing_hint": "h",
    "required_flag": true, "recommended_flag": false,
    "content_type": "text", "keyword_hint": ["供应链"]
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
        "related_regulations": ["ISO9001"],
        "overall_strategy": "强调仓配能力",
        "common_mistakes": "忽视应急预案",
        "template_style": "formal",
        "usual_page_range": "5-8页",
        "status": "active",
        "nodes": [
            {
                "node_title": "总体设计",
                "node_level": 1,
                "node_order": 1,
                "importance_level": "required",
                "purpose": "p",
                "writing_goal": "g",
                "writing_hint": "h",
                "content_type": "text",
                "keyword_hint": ["供应链"],
                "children": [],
            }
        ],
    }


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
