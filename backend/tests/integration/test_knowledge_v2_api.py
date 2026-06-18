from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.doc_chunk.content_md_store import persist_content_md


def _seed_file_import(db_session, kb_id):
    row = FileImport(
        kb_id=kb_id,
        file_name="knowledge-v2-api.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path="/tmp/knowledge-v2-api.docx",
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
        document_name="knowledge-v2-api.docx",
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
        title="第一章 总则",
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
        title="1.1 投标范围",
        level=2,
        sort_order=1,
        tree_version=1,
    )
    db_session.add_all([parent, child])
    db_session.commit()
    return document, parent, child


def _seed_content_md(tmp_path, document_id):
    source = tmp_path / "content.md"
    source.write_text(
        "# 第一章 总则\n\n这是父节点内容。\n\n## 1.1 投标范围\n\n这是子节点内容。\n",
        encoding="utf-8",
    )
    persisted = persist_content_md(document_id=document_id, source_path=Path(source))
    assert persisted is not None


def _create_payload(doc_id, node_id, *, title: str, summary: str):
    return {
        "doc_id": str(doc_id),
        "primary_node_id": str(node_id),
        "title": title,
        "content": "知识正文内容",
        "summary": summary,
        "knowledge_type": "fact",
        "content_type": "text",
        "source_type": "bid",
        "file_name": "knowledge-v2-api.docx",
        "project_name": "测试项目",
        "page_start": 1,
        "page_end": 2,
        "char_start": 0,
        "char_end": 16,
        "parent_id": None,
        "need_parent_context": False,
        "quote_mode": "full",
        "category": "technical",
        "tags": ["投标", "技术"],
        "products": ["产品A"],
        "industries": ["行业A"],
        "customer_types": ["客户A"],
        "regions": ["华东"],
        "issue_date": None,
        "expire_date": None,
        "status": "draft",
        "is_template": False,
        "template_type": None,
        "variables": [],
        "is_immutable": False,
        "exclusion_rules": [],
        "retrieval_weight": 1.0,
        "security_level": "internal",
        "owner": "tester",
        "review_status": "approved",
        "winning_flag": False,
        "edit_distance_avg": None,
        "force": False,
    }


def test_knowledge_v2_preview_returns_200(client, db_session, seeded_kb, tmp_path):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(tmp_path, document.document_id)

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/entry/documents/"
        f"{document.document_id}/nodes/{parent.node_id}/preview"
    )

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["title"] == "第一章 总则"
    assert "父节点内容" in payload["content_md"]


def test_knowledge_v2_create_returns_201(client, db_session, seeded_kb, tmp_path):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(tmp_path, document.document_id)
    payload = _create_payload(
        document.document_id,
        parent.node_id,
        title="网络架构要求",
        summary="网络架构摘要",
    )

    resp = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks", json=payload)

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["version"] == "1.0"
    assert data["id"] is not None
    assert data["knowledge_code"]


def test_knowledge_v2_duplicate_returns_409(client, db_session, seeded_kb, tmp_path):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(tmp_path, document.document_id)
    payload = _create_payload(
        document.document_id,
        parent.node_id,
        title="重复测试",
        summary="重复摘要",
    )
    first = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks", json=payload)
    assert first.status_code == 201

    second = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks", json=payload)
    assert second.status_code == 409
    err = second.json()["error"]
    assert err["code"] == "CHUNK_CONFLICT"
    assert err["details"]["existing_version"] == "1.0"


def test_knowledge_v2_force_create_returns_11(client, db_session, seeded_kb, tmp_path):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(tmp_path, document.document_id)
    payload = _create_payload(
        document.document_id,
        parent.node_id,
        title="版本覆盖测试",
        summary="首版摘要",
    )
    first = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks", json=payload)
    assert first.status_code == 201

    payload["summary"] = "覆盖版摘要"
    payload["force"] = True
    second = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks", json=payload)
    assert second.status_code == 201
    assert second.json()["data"]["version"] == "1.1"


def test_knowledge_v2_list_supports_keyword_filter(client, db_session, seeded_kb, tmp_path):
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(tmp_path, document.document_id)

    payload_1 = _create_payload(
        document.document_id,
        parent.node_id,
        title="网络架构要求",
        summary="网络设备参数",
    )
    payload_2 = _create_payload(
        document.document_id,
        child.node_id,
        title="服务方案说明",
        summary="售后服务内容",
    )
    first = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks", json=payload_1)
    second = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks", json=payload_2)
    assert first.status_code == 201
    assert second.status_code == 201

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks",
        params={"keyword": "网络", "page": 1, "page_size": 20},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "网络架构要求"
