from pathlib import Path

from src.services.docx_document_walker import walk_document

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-actual-bid.docx"


def test_walk_document_returns_heading_and_paragraph_nodes():
    result = walk_document(FIXTURE)
    node_types = {n.node_type for n in result.nodes}
    assert "heading" in node_types
    assert "paragraph" in node_types
    headings = [n for n in result.nodes if n.node_type == "heading"]
    assert all(h.level >= 1 for h in headings)
