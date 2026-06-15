import json
from pathlib import Path
from uuid import uuid4

from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.doc_chunk.mappers.document_tree import import_document_tree
from src.services.doc_chunk.types import ImportContext
from src.services.doc_chunk.workspace_loader import load_workspace

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_import_document_tree_unique_uuids_and_parents(db_session, seeded_kb):
    loaded = load_workspace(FIXTURE_ROOT)
    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=uuid4(),
        source_type=DocumentSourceType.actual_bid,
        document_name="t.docx",
        parse_status=DocumentParseStatus.parsing,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    ctx = ImportContext(workspace_path=FIXTURE_ROOT)
    tree_id_map = import_document_tree(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        tree_payload=loaded.document_tree,
    )
    assert len(tree_id_map) == 3
    assert len(set(tree_id_map.values())) == 3

    nodes = (
        db_session.query(DocumentTreeNode)
        .filter(DocumentTreeNode.document_id == document.document_id)
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    assert nodes[1].parent_id == nodes[0].node_id
    headings = [n for n in nodes if n.node_type == DocumentTreeNodeType.heading]
    assert len(headings) == 2
