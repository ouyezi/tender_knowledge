from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.doc_chunk.mappers.document_tree import import_document_tree
from src.services.doc_chunk.outline_heading_correction import apply_outline_heading_corrections
from src.services.doc_chunk.types import ImportContext
from src.services.doc_chunk.workspace_loader import load_workspace

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_wrong_tree"


def test_import_document_tree_applies_outline_heading_corrections(db_session, seeded_kb):
    loaded = load_workspace(FIXTURE_ROOT)
    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=uuid4(),
        source_type=DocumentSourceType.actual_bid,
        document_name="wrong-tree.docx",
        parse_status=DocumentParseStatus.parsing,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    ctx = ImportContext(workspace_path=FIXTURE_ROOT)
    import_document_tree(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        tree_payload=loaded.document_tree,
        outline_payload=loaded.outline,
    )

    nodes = (
        db_session.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.document_id == document.document_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    by_title = {node.title: node for node in nodes}

    assert by_title["1.2 合同附件"].level == 2
    assert by_title["1.2.1 合同扫描件"].parent_id == by_title["1.2 合同附件"].node_id


def test_apply_outline_heading_corrections_updates_existing_tree(db_session, seeded_kb):
    loaded = load_workspace(FIXTURE_ROOT)
    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=uuid4(),
        source_type=DocumentSourceType.actual_bid,
        document_name="wrong-tree.docx",
        parse_status=DocumentParseStatus.parsing,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    ctx = ImportContext(workspace_path=FIXTURE_ROOT)
    import_document_tree(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        tree_payload=loaded.document_tree,
        outline_payload=None,
    )

    updated = apply_outline_heading_corrections(
        db_session,
        document_id=document.document_id,
        outline_payload=loaded.outline,
        outline_node_to_tree_id=dict(ctx.outline_node_id_to_tree_id),
    )
    assert updated >= 2

    nodes = (
        db_session.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.document_id == document.document_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    by_title = {node.title: node for node in nodes}
    assert by_title["1.2.1 合同扫描件"].parent_id == by_title["1.2 合同附件"].node_id
