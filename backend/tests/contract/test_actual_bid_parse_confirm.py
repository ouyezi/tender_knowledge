from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType


def _seed_parse_ready_actual_bid_task(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="actual-bid.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{seeded_kb.kb_id}/actual-bid.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="actual-bid.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    outline = BidOutline(
        kb_id=seeded_kb.kb_id,
        source_doc_id=document.document_id,
        import_id=file_import.import_id,
        outline_name="原始目录",
        created_by="admin",
    )
    db_session.add(outline)
    db_session.flush()

    node_1 = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="原始章节1",
        level=1,
        sort_order=0,
    )
    node_2 = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="原始章节2",
        level=1,
        sort_order=1,
    )
    db_session.add_all([node_1, node_2])
    db_session.flush()

    parse_task = ActualBidParseTask(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        document_id=document.document_id,
        bid_outline_id=outline.bid_outline_id,
        status=ActualBidParseTaskStatus.ready,
        created_by="admin",
    )
    db_session.add(parse_task)
    db_session.commit()
    db_session.refresh(parse_task)
    db_session.refresh(outline)
    db_session.refresh(node_1)
    db_session.refresh(node_2)
    db_session.refresh(document)
    return parse_task, document, outline, node_1, node_2


def test_confirm_wizard_sets_confirmed_without_structure_lock(client, db_session, seeded_kb):
    parse_task, document, outline, node_1, node_2 = _seed_parse_ready_actual_bid_task(
        db_session, seeded_kb
    )

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/actual-bid-parse/tasks/{parse_task.parse_task_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "document": {
                "bid_project_name": "测试项目",
                "bid_customer_name": "测试客户",
                "product_category_ids": [],
            },
            "outline_nodes": [
                {
                    "outline_node_id": str(node_1.outline_node_id),
                    "parent_id": None,
                    "title": "1. 技术方案",
                    "level": 1,
                    "sort_order": 0,
                    "chapter_taxonomy_id": None,
                    "product_category_ids": [],
                    "needs_manual_review": False,
                },
                {
                    "outline_node_id": str(node_2.outline_node_id),
                    "parent_id": str(node_1.outline_node_id),
                    "title": "1.1 总体架构",
                    "level": 2,
                    "sort_order": 0,
                    "chapter_taxonomy_id": None,
                    "product_category_ids": [],
                    "needs_manual_review": False,
                },
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "confirmed"
    assert data["parse_task_id"] == str(parse_task.parse_task_id)
    assert data["bid_outline_id"] == str(outline.bid_outline_id)
    assert data["structure_locked_at"] is None
    assert data["updated_outline_nodes"] == 2

    db_session.expire_all()
    refreshed_task = db_session.get(ActualBidParseTask, parse_task.parse_task_id)
    refreshed_document = db_session.get(Document, document.document_id)
    refreshed_outline = db_session.get(BidOutline, outline.bid_outline_id)
    refreshed_node_1 = db_session.get(BidOutlineNode, node_1.outline_node_id)
    refreshed_node_2 = db_session.get(BidOutlineNode, node_2.outline_node_id)

    assert refreshed_task is not None
    assert refreshed_task.status == ActualBidParseTaskStatus.confirmed
    assert refreshed_document is not None
    assert refreshed_document.bid_project_name == "测试项目"
    assert refreshed_document.bid_customer_name == "测试客户"
    assert refreshed_document.confirmed_metadata is True
    assert refreshed_outline is not None
    assert refreshed_outline.structure_locked_at is None
    assert refreshed_node_1 is not None
    assert refreshed_node_1.title == "1. 技术方案"
    assert refreshed_node_2 is not None
    assert refreshed_node_2.parent_id == refreshed_node_1.outline_node_id
