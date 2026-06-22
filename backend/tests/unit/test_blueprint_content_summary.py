from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.knowledge.blueprint_generate_service import (
    aggregate_content_summary,
    collect_subtree_outline,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_tree_with_body(db_session, kb_id):
    file_import = FileImport(
        kb_id=kb_id,
        file_name="summary.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path="/tmp/summary.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        source_usage=DocumentSourceUsage.knowledge_extract,
        document_name="summary.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()

    root_id = uuid4()
    child_heading_id = uuid4()
    root = DocumentTreeNode(
        node_id=root_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="第一章",
        level=1,
        sort_order=0,
        tree_version=1,
    )
    child_heading = DocumentTreeNode(
        node_id=child_heading_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=root_id,
        node_type=DocumentTreeNodeType.heading,
        title="1.1 技术方案",
        level=2,
        sort_order=1,
        tree_version=1,
    )
    paragraph = DocumentTreeNode(
        node_id=uuid4(),
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=child_heading_id,
        node_type=DocumentTreeNodeType.paragraph,
        title=None,
        level=None,
        sort_order=2,
        content_preview="总体架构采用微服务部署。",
        tree_version=1,
    )
    db_session.add_all([root, child_heading, paragraph])
    db_session.commit()
    return document, root, child_heading


def test_aggregate_content_summary_joins_non_heading_previews():
    nodes = [
        type("N", (), {
            "node_id": uuid4(),
            "parent_id": None,
            "node_type": DocumentTreeNodeType.heading,
            "sort_order": 0,
            "content_preview": None,
        })(),
        type("N", (), {
            "node_id": uuid4(),
            "parent_id": None,
            "node_type": DocumentTreeNodeType.paragraph,
            "sort_order": 1,
            "content_preview": "第一段。",
        })(),
        type("N", (), {
            "node_id": uuid4(),
            "parent_id": None,
            "node_type": DocumentTreeNodeType.paragraph,
            "sort_order": 2,
            "content_preview": "第二段。",
        })(),
    ]
    root_id = nodes[0].node_id
    nodes[1].parent_id = root_id
    nodes[2].parent_id = root_id

    summary = aggregate_content_summary(nodes, root_id=root_id)
    assert "第一段" in summary
    assert "第二段" in summary


def test_collect_subtree_outline_includes_content_summary(db_session, seeded_kb):
    document, root, child_heading = _seed_tree_with_body(db_session, seeded_kb.kb_id)

    outline = collect_subtree_outline(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=root.node_id,
    )

    child = outline["children"][0]
    assert child["node_title"] == "1.1 技术方案"
    assert "微服务" in child.get("content_summary", "")
    assert "微服务" in outline.get("content_summary", "")
