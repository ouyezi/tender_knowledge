from uuid import uuid4

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from tests.contract.test_bid_outline_nodes import _seed_outline_with_nodes


def test_get_outline_node_content(client, db_session, seeded_kb):
    outline, root_a, _, root_c, child_c, _ = _seed_outline_with_nodes(db_session, seeded_kb)

    p = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=outline.source_doc_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.paragraph,
        sort_order=1,
        content_preview="第一章正文",
        tree_version=1,
    )
    db_session.add(p)
    db_session.commit()

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/nodes/{root_c.outline_node_id}/content",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["outline_node_id"] == str(root_c.outline_node_id)
    assert data["title"] == "第三章"
    assert len(data["sections"]) == 2
    assert data["sections"][0]["title"] == "第三章"
    assert data["sections"][1]["title"] == "第三章-子章节"


def test_get_outline_node_content_not_found(client, db_session, seeded_kb):
    outline, _, _, _, _, _ = _seed_outline_with_nodes(db_session, seeded_kb)
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/nodes/{uuid4()}/content",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "OUTLINE_NODE_NOT_FOUND"
