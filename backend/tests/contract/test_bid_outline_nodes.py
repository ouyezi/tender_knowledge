from src.models.actual_bid_audit_log import ActualBidAuditLog
from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType


def _seed_outline_with_nodes(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="outline-source.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{seeded_kb.kb_id}/outline-source.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="outline-source.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    outline = BidOutline(
        kb_id=seeded_kb.kb_id,
        source_doc_id=document.document_id,
        import_id=file_import.import_id,
        outline_name="测试目录",
        created_by="admin",
    )
    db_session.add(outline)
    db_session.flush()

    root_a = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="第一章",
        level=1,
        sort_order=0,
    )
    root_b = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="第二章",
        level=1,
        sort_order=1,
    )
    root_c = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="第三章",
        level=1,
        sort_order=2,
    )
    db_session.add_all([root_a, root_b, root_c])
    db_session.flush()

    child_c = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=root_c.outline_node_id,
        title="第三章-子章节",
        level=2,
        sort_order=0,
    )
    db_session.add(child_c)
    db_session.flush()

    source_tree_node = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="文档原始第一章",
        level=1,
        sort_order=0,
        tree_version=1,
        is_outline_node=True,
    )
    db_session.add(source_tree_node)
    db_session.flush()

    root_a.source_node_id = source_tree_node.node_id
    db_session.commit()
    return outline, root_a, root_b, root_c, child_c, source_tree_node


def test_get_bid_outline_detail_and_nodes(client, db_session, seeded_kb):
    outline, root_a, _, _, _, _ = _seed_outline_with_nodes(db_session, seeded_kb)

    detail_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    assert detail_data["bid_outline_id"] == str(outline.bid_outline_id)
    assert detail_data["outline_name"] == "测试目录"
    assert len(detail_data["root_nodes"]) == 3
    assert detail_data["root_nodes"][0]["outline_node_id"] == str(root_a.outline_node_id)

    nodes_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/nodes",
        headers={"X-Operator-Id": "admin"},
    )
    assert nodes_resp.status_code == 200
    nodes_data = nodes_resp.json()["data"]
    assert nodes_data["bid_outline_id"] == str(outline.bid_outline_id)
    assert len(nodes_data["nodes"]) == 4


def test_patch_outline_node_title_does_not_change_document_tree_title(client, db_session, seeded_kb):
    outline, root_a, _, _, _, source_tree_node = _seed_outline_with_nodes(db_session, seeded_kb)

    patch_resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/nodes/{root_a.outline_node_id}",
        headers={"X-Operator-Id": "admin"},
        json={"title": "第一章(人工修订)"},
    )
    assert patch_resp.status_code == 200
    patch_data = patch_resp.json()["data"]
    assert patch_data["node"]["title"] == "第一章(人工修订)"
    assert patch_data["audit_id"]

    db_session.expire_all()
    refreshed_outline_node = db_session.get(BidOutlineNode, root_a.outline_node_id)
    refreshed_source_node = db_session.get(DocumentTreeNode, source_tree_node.node_id)
    assert refreshed_outline_node is not None
    assert refreshed_source_node is not None
    assert refreshed_outline_node.title == "第一章(人工修订)"
    assert refreshed_source_node.title == "文档原始第一章"

    audit = (
        db_session.query(ActualBidAuditLog)
        .filter(
            ActualBidAuditLog.kb_id == seeded_kb.kb_id,
            ActualBidAuditLog.object_type == "bid_outline_node",
            ActualBidAuditLog.object_id == root_a.outline_node_id,
            ActualBidAuditLog.action == "outline_node_patch",
        )
        .one_or_none()
    )
    assert audit is not None


def test_batch_operate_outline_nodes_delete_merge_reorder(client, db_session, seeded_kb):
    outline, root_a, root_b, root_c, child_c, _ = _seed_outline_with_nodes(db_session, seeded_kb)
    root_a_id = root_a.outline_node_id
    root_b_id = root_b.outline_node_id
    root_c_id = root_c.outline_node_id
    child_c_id = child_c.outline_node_id

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/nodes/batch",
        headers={"X-Operator-Id": "admin"},
        json={
            "operations": [
                {
                    "op": "merge",
                    "source_node_ids": [str(root_a_id), str(root_b_id)],
                    "target_title": "第一二章(合并)",
                },
                {
                    "op": "reorder",
                    "parent_id": None,
                    "ordered_node_ids": [str(root_c_id), str(root_a_id)],
                },
                {"op": "delete", "outline_node_id": str(root_c_id)},
            ]
        },
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["audit_id"]

    db_session.expire_all()
    refreshed_a = db_session.get(BidOutlineNode, root_a_id)
    refreshed_b = db_session.get(BidOutlineNode, root_b_id)
    refreshed_c = db_session.get(BidOutlineNode, root_c_id)
    refreshed_child_c = db_session.get(BidOutlineNode, child_c_id)
    assert refreshed_a is not None
    assert refreshed_a.title == "第一二章(合并)"
    assert refreshed_b is None
    assert refreshed_c is None
    assert refreshed_child_c is None

    audit = (
        db_session.query(ActualBidAuditLog)
        .filter(
            ActualBidAuditLog.kb_id == seeded_kb.kb_id,
            ActualBidAuditLog.object_type == "bid_outline",
            ActualBidAuditLog.object_id == outline.bid_outline_id,
            ActualBidAuditLog.action == "outline_nodes_batch",
        )
        .one_or_none()
    )
    assert audit is not None
