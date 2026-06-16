# backend/tests/unit/test_outline_node_content_service.py
from uuid import uuid4

import pytest

from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.content_blocks import parse_content
from src.services.outline_node_content_service import (
    OutlineNodeNotFoundError,
    OutlineNotFoundError,
    build_outline_subtree_content,
)


def _seed_outline_tree(db_session, kb_id):
    file_import = FileImport(
        kb_id=kb_id,
        file_name="content.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{kb_id}/content.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="content.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    outline = BidOutline(
        kb_id=kb_id,
        source_doc_id=document.document_id,
        import_id=file_import.import_id,
        outline_name="测试目录",
        created_by="admin",
    )
    db_session.add(outline)
    db_session.flush()

    h1_tree = DocumentTreeNode(
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="父章节",
        level=1,
        sort_order=0,
        tree_version=1,
    )
    p1_tree = DocumentTreeNode(
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.paragraph,
        sort_order=1,
        content_preview="父正文",
        tree_version=1,
    )
    h2_tree = DocumentTreeNode(
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="子章节",
        level=2,
        sort_order=2,
        tree_version=1,
    )
    p2_tree = DocumentTreeNode(
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.paragraph,
        sort_order=3,
        content_preview="子正文",
        tree_version=1,
    )
    db_session.add_all([h1_tree, p1_tree, h2_tree, p2_tree])
    db_session.flush()

    parent = BidOutlineNode(
        kb_id=kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="父目录",
        level=1,
        sort_order=0,
        source_node_id=h1_tree.node_id,
    )
    db_session.add(parent)
    db_session.flush()

    child = BidOutlineNode(
        kb_id=kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=parent.outline_node_id,
        title="子目录",
        level=2,
        sort_order=0,
        source_node_id=h2_tree.node_id,
    )
    no_source = BidOutlineNode(
        kb_id=kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=parent.outline_node_id,
        title="无源节点",
        level=2,
        sort_order=1,
        source_node_id=None,
    )
    db_session.add_all([child, no_source])
    db_session.commit()
    return outline, document, parent, child, no_source


def test_build_outline_subtree_content_parent_includes_descendants(db_session, seeded_kb):
    outline, _, parent, child, no_source = _seed_outline_tree(db_session, seeded_kb.kb_id)

    result = build_outline_subtree_content(
        db_session,
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        outline_node_id=parent.outline_node_id,
    )

    assert result["outline_node_id"] == str(parent.outline_node_id)
    assert result["title"] == "父目录"
    assert len(result["sections"]) == 3
    assert [s["title"] for s in result["sections"]] == ["父目录", "子目录", "无源节点"]

    parent_section = result["sections"][0]
    child_section = result["sections"][1]
    no_source_section = result["sections"][2]

    parent_doc = parse_content(parent_section["content"])
    assert [b.get("text") for b in parent_doc.blocks if b.get("type") == "paragraph"] == ["父正文"]
    assert parent_section["has_content"] is True

    child_doc = parse_content(child_section["content"])
    assert [b.get("text") for b in child_doc.blocks if b.get("type") == "paragraph"] == ["子正文"]
    assert child_section["has_content"] is True

    assert no_source_section["has_content"] is False
    assert no_source_section["empty_reason"] == "no_source_node"


def test_build_outline_subtree_content_leaf_only_self(db_session, seeded_kb):
    outline, _, parent, child, _ = _seed_outline_tree(db_session, seeded_kb.kb_id)

    result = build_outline_subtree_content(
        db_session,
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        outline_node_id=child.outline_node_id,
    )

    assert len(result["sections"]) == 1
    assert result["sections"][0]["title"] == "子目录"


def test_build_outline_subtree_content_empty_body(db_session, seeded_kb):
    outline, document, parent, _, _ = _seed_outline_tree(db_session, seeded_kb.kb_id)
    empty_heading = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="空节",
        level=1,
        sort_order=10,
        tree_version=1,
    )
    db_session.add(empty_heading)
    db_session.flush()
    parent.source_node_id = empty_heading.node_id
    db_session.commit()

    result = build_outline_subtree_content(
        db_session,
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        outline_node_id=parent.outline_node_id,
    )

    assert result["sections"][0]["has_content"] is False
    assert result["sections"][0]["empty_reason"] == "empty_body"


def test_build_outline_subtree_content_outline_not_found(db_session, seeded_kb):
    with pytest.raises(OutlineNotFoundError):
        build_outline_subtree_content(
            db_session,
            kb_id=seeded_kb.kb_id,
            bid_outline_id=uuid4(),
            outline_node_id=uuid4(),
        )


def test_build_outline_subtree_content_node_not_found(db_session, seeded_kb):
    outline, _, _, _, _ = _seed_outline_tree(db_session, seeded_kb.kb_id)
    with pytest.raises(OutlineNodeNotFoundError):
        build_outline_subtree_content(
            db_session,
            kb_id=seeded_kb.kb_id,
            bid_outline_id=outline.bid_outline_id,
            outline_node_id=uuid4(),
        )
