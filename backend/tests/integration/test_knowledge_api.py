from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.doc_chunk.content_md_store import persist_content_md
from src.services.doc_chunk.outline_store import persist_outline, persist_outline_node_map
from tests.helpers.chunk_payload import minimal_chunk_payload


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


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


def _seed_content_md(tmp_path, document_id, *, parent=None, child=None, monkeypatch=None):
    content_md = (
        "# 第一章 总则\n\n这是父节点内容。\n\n## 1.1 投标范围\n\n这是子节点内容。\n"
    )
    if monkeypatch is not None:
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    source = tmp_path / "content.md"
    source.write_text(content_md, encoding="utf-8")
    persisted = persist_content_md(document_id=document_id, source_path=Path(source))
    assert persisted is not None
    if parent is not None:
        parent_start = content_md.index("# 第一章")
        nodes = [
            {
                "node_id": "n1",
                "title": parent.title,
                "level": parent.level,
                "parent_id": None,
                "sort_order": parent.sort_order,
                "anchor": {"char_start": parent_start, "char_end": parent_start + 5},
            }
        ]
        mapping = {"n1": parent.node_id}
        if child is not None:
            child_start = content_md.index("## 1.1")
            nodes.append(
                {
                    "node_id": "n2",
                    "title": child.title,
                    "level": child.level,
                    "parent_id": "n1",
                    "sort_order": child.sort_order,
                    "anchor": {"char_start": child_start, "char_end": child_start + 5},
                }
            )
            mapping["n2"] = child.node_id
        persist_outline(document_id=document_id, outline_payload={"nodes": nodes})
        persist_outline_node_map(
            document_id=document_id,
            outline_node_to_tree_id=mapping,
        )


def _create_payload(doc_id, node_id, *, title: str, summary: str):
    payload = minimal_chunk_payload(
        title=title,
        summary=summary,
        file_name="knowledge-v2-api.docx",
        tags=["投标", "技术"],
        regions=["华东"],
        owner="tester",
    )
    payload.update(
        {
            "doc_id": str(doc_id),
            "primary_node_id": str(node_id),
            "content": "知识正文内容",
            "force": False,
        }
    )
    return payload


def test_knowledge_preview_returns_200(client, db_session, seeded_kb, seeded_taxonomy, tmp_path, monkeypatch):
    _ = seeded_taxonomy
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(
        tmp_path,
        document.document_id,
        parent=parent,
        child=child,
        monkeypatch=monkeypatch,
    )

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/entry/documents/"
        f"{document.document_id}/nodes/{parent.node_id}/preview"
    )

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["title"] == "第一章 总则"
    assert "父节点内容" in payload["content_md"]


def test_knowledge_create_returns_201(client, db_session, seeded_kb, seeded_taxonomy, tmp_path):
    _ = seeded_taxonomy
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


def test_knowledge_duplicate_returns_409(client, db_session, seeded_kb, seeded_taxonomy, tmp_path):
    _ = seeded_taxonomy
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


def test_knowledge_force_create_returns_11(client, db_session, seeded_kb, seeded_taxonomy, tmp_path):
    _ = seeded_taxonomy
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


def test_knowledge_list_supports_keyword_filter(client, db_session, seeded_kb, seeded_taxonomy, tmp_path):
    _ = seeded_taxonomy
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


def test_create_chunk_returns_taxonomy_fields(client, db_session, seeded_kb, seeded_taxonomy, tmp_path):
    _ = seeded_taxonomy
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(tmp_path, document.document_id)
    payload = _create_payload(
        document.document_id,
        parent.node_id,
        title="分类测试",
        summary="分类摘要",
    )
    payload["block_type_code"] = "official_template"
    payload["application_type_code"] = "template_fill"
    payload["business_line_codes"] = ["insurance"]

    resp = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks", json=payload)
    assert resp.status_code == 201
    chunk_id = resp.json()["data"]["id"]

    detail = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/{chunk_id}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["block_type_code"] == "official_template"
    assert data["block_type_label"] == "官方模版"
    assert data["application_type_code"] == "template_fill"
    assert data["application_type_label"] == "模版填充"
    assert data["business_line_codes"] == ["insurance"]
    assert data["business_line_labels"] == ["保险"]
    assert "is_expired" in data


def test_chunk_detail_excludes_internal_char_fields(
    client, db_session, seeded_kb, seeded_taxonomy, tmp_path
):
    _ = seeded_taxonomy
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(tmp_path, document.document_id)
    create = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks",
        json={
            "doc_id": str(document.document_id),
            "primary_node_id": str(parent.node_id),
            "title": "T",
            "content": "正文",
            "knowledge_type": "fact",
            "block_type_code": "ip_patent",
            "application_type_code": "fixed_reference",
            "business_line_codes": ["general"],
            "qualification_info": "ISO9001|NO-1|2024-01-01|2026-01-01",
        },
    )
    assert create.status_code == 201
    chunk_id = create.json()["data"]["id"]
    detail = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/{chunk_id}").json()["data"]
    assert detail["qualification_info"] == "ISO9001|NO-1|2024-01-01|2026-01-01"
    assert "char_start" not in detail
    assert "section_char_start" in detail
    assert "page_start" not in detail
    assert "winning_flag" not in detail
    assert "issue_date" not in detail


def test_mark_chunks_index_failed_api(client, db_session, seeded_kb):
    from uuid import uuid4

    from src.models.knowledge_chunk import KnowledgeChunk
    from tests.helpers.chunk_payload import minimal_chunk_orm_kwargs

    chunk = KnowledgeChunk(
        id=501,
        kb_id=seeded_kb.kb_id,
        knowledge_code=str(uuid4()),
        version="1.0",
        is_latest=True,
        doc_id=uuid4(),
        primary_node_id=str(uuid4()),
        content_hash="hash-501",
        token_count=3,
        embedding_status="indexing",
        **minimal_chunk_orm_kwargs(),
    )
    db_session.add(chunk)
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/mark-index-failed",
        json={"chunk_ids": [501, 502]},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["updated_ids"] == [501]
    assert body["skipped_ids"] == [502]

    db_session.refresh(chunk)
    assert chunk.embedding_status == "failed"
