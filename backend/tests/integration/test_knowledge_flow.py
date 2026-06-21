from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.doc_chunk.content_md_store import persist_content_md
from src.services.knowledge.asset_seed_service import seed_chunk_assets_from_workspace

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def _seed_file_import(db_session, kb_id):
    row = FileImport(
        kb_id=kb_id,
        file_name="knowledge-v2-flow.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path="/tmp/knowledge-v2-flow.docx",
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
        document_name="knowledge-v2-flow.docx",
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


def _seed_chunk_assets_optional(tmp_path, db_session, kb_id, doc_id):
    workspace = tmp_path / "workspace"
    shutil.copytree(FIXTURE_ROOT, workspace)

    images_manifest = {
        "schema_version": "1.0",
        "images": [
            {
                "image_ref": "images/figure-1.png",
                "char_start": 2,
                "char_end": 8,
            }
        ],
    }
    (workspace / "images" / "manifest.json").write_text(
        json.dumps(images_manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    chunk_path = workspace / "chunks" / "chunk-0002.json"
    chunk_payload = json.loads(chunk_path.read_text(encoding="utf-8"))
    chunk_payload["blocks"] = list(chunk_payload.get("blocks") or []) + [
        {
            "type": "table",
            "markdown": "|字段|值|\n|---|---|\n|范围|华东|",
            "char_start": 4,
            "char_end": 14,
        }
    ]
    chunk_path.write_text(json.dumps(chunk_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return seed_chunk_assets_from_workspace(
        db_session,
        kb_id=kb_id,
        doc_id=doc_id,
        workspace_path=workspace,
    )


def _create_payload(doc_id, node_id, *, summary: str, force: bool = False):
    return {
        "doc_id": str(doc_id),
        "primary_node_id": str(node_id),
        "title": "网络架构要求",
        "content": "知识正文内容",
        "summary": summary,
        "knowledge_type": "fact",
        "content_type": "text",
        "source_type": "bid",
        "file_name": "knowledge-v2-flow.docx",
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
        "force": force,
    }


def test_knowledge_full_regression_flow(client, db_session, seeded_kb, tmp_path):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    _seed_content_md(tmp_path, document.document_id)
    seeded_assets = _seed_chunk_assets_optional(
        tmp_path=tmp_path,
        db_session=db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
    )
    assert seeded_assets >= 1
    db_session.commit()

    preview_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/entry/documents/"
        f"{document.document_id}/nodes/{parent.node_id}/preview"
    )
    assert preview_resp.status_code == 200
    preview_data = preview_resp.json()["data"]
    assert preview_data["title"] == "第一章 总则"
    assert "父节点内容" in preview_data["content_md"]

    create_payload = _create_payload(document.document_id, parent.node_id, summary="网络架构摘要")
    create_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks",
        json=create_payload,
    )
    assert create_resp.status_code == 201
    created = create_resp.json()["data"]
    assert created["version"] == "1.0"
    chunk_id = created["id"]

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks",
        params={"keyword": "网络", "page": 1, "page_size": 20},
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()["data"]
    assert list_data["total"] == 1
    assert len(list_data["items"]) == 1
    assert list_data["items"][0]["id"] == chunk_id
    assert list_data["items"][0]["title"] == "网络架构要求"
    assert list_data["items"][0]["version"] == "1.0"

    detail_resp = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/{chunk_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["id"] == chunk_id
    assert detail["version"] == "1.0"
    assert detail["primary_node_id"] == str(parent.node_id)
    assert len(detail["assets"]) >= 1
    assert all(asset["chunk_id"] == chunk_id for asset in detail["assets"])

    force_payload = _create_payload(
        document.document_id,
        parent.node_id,
        summary="网络架构摘要-覆盖版",
        force=True,
    )
    force_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks",
        json=force_payload,
    )
    assert force_resp.status_code == 201
    force_data = force_resp.json()["data"]
    assert force_data["version"] == "1.1"
    assert force_data["previous_version_id"] == chunk_id
    overwritten_id = force_data["id"]

    overwritten_detail_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks/{overwritten_id}"
    )
    assert overwritten_detail_resp.status_code == 200
    overwritten_detail = overwritten_detail_resp.json()["data"]
    assert overwritten_detail["version"] == "1.1"
    assert overwritten_detail["summary"] == "网络架构摘要-覆盖版"
    assert overwritten_detail["previous_version"]["id"] == chunk_id
    assert overwritten_detail["previous_version"]["version"] == "1.0"

    final_list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-chunks",
        params={"keyword": "网络", "page": 1, "page_size": 20},
    )
    assert final_list_resp.status_code == 200
    final_list_data = final_list_resp.json()["data"]
    assert final_list_data["total"] == 1
    assert len(final_list_data["items"]) == 1
    assert final_list_data["items"][0]["id"] == overwritten_id
    assert final_list_data["items"][0]["version"] == "1.1"
