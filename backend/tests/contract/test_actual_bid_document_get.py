from pathlib import Path

from src.config import Settings
from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.bid_outline import BidOutline
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.actual_bid_parse_runner import run_actual_bid_parse_pending


def _seed_confirmed_actual_bid_import_with_downstreams(db_session, seeded_kb, sample_docx_path):
    storage_rel = f"{seeded_kb.kb_id}/sample-actual-bid.docx"
    storage_abs = Path(Settings().storage_root) / storage_rel
    storage_abs.parent.mkdir(parents=True, exist_ok=True)
    storage_abs.write_bytes(sample_docx_path.read_bytes())

    record = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="sample-actual-bid.docx",
        file_type=FileType.docx,
        file_size=storage_abs.stat().st_size,
        storage_path=storage_rel,
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(record)
    db_session.flush()
    for task_type in (
        DownstreamTaskType.document_parse,
        DownstreamTaskType.bid_outline_extract,
        DownstreamTaskType.candidate_knowledge_generate,
    ):
        db_session.add(
            DownstreamTaskEntry(
                kb_id=seeded_kb.kb_id,
                import_id=record.import_id,
                task_type=task_type,
                status=DownstreamTaskStatus.pending,
            )
        )
    db_session.commit()
    return record


def test_get_document_and_tree_after_parse(client, db_session, seeded_kb):
    sample_docx_path = Path(__file__).resolve().parent.parent / "fixtures" / "sample-actual-bid.docx"
    record = _seed_confirmed_actual_bid_import_with_downstreams(
        db_session, seeded_kb, sample_docx_path
    )
    run_actual_bid_parse_pending(db_session)

    task = (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == record.import_id)
        .order_by(ActualBidParseTask.created_at.desc())
        .first()
    )
    assert task is not None
    assert task.status == ActualBidParseTaskStatus.ready
    assert task.document_id is not None
    assert task.bid_outline_id is not None

    document_id = task.document_id
    kb_id = seeded_kb.kb_id

    detail = client.get(
        f"/api/v1/kbs/{kb_id}/actual-bid-parse/documents/{document_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["document_id"] == str(document_id)
    assert detail_data["import_id"] == str(record.import_id)
    assert detail_data["source_type"] == DocumentSourceType.actual_bid.value
    assert detail_data["parse_status"] == DocumentParseStatus.ready.value
    assert detail_data["bid_outline_id"] == str(task.bid_outline_id)

    tree = client.get(
        f"/api/v1/kbs/{kb_id}/actual-bid-parse/documents/{document_id}/tree",
        headers={"X-Operator-Id": "admin"},
    )
    assert tree.status_code == 200
    tree_data = tree.json()["data"]
    assert tree_data["document_id"] == str(document_id)
    assert tree_data["tree_version"] == detail_data["tree_version"]
    assert len(tree_data["nodes"]) > 0
    assert tree_data["nodes"][0]["node_type"] in {
        DocumentTreeNodeType.heading.value,
        DocumentTreeNodeType.paragraph.value,
        DocumentTreeNodeType.other.value,
    }

    task_detail = client.get(
        f"/api/v1/kbs/{kb_id}/actual-bid-parse/tasks/{task.parse_task_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert task_detail.status_code == 200
    task_data = task_detail.json()["data"]
    assert "outline_quality" in task_data
    assert "filtered_total" in task_data
    assert "file_name" in task_data

def test_patch_document_metadata(client, db_session, seeded_kb):
    storage_rel = f"{seeded_kb.kb_id}/bid.docx"
    storage_abs = Path(Settings().storage_root) / storage_rel
    storage_abs.parent.mkdir(parents=True, exist_ok=True)
    storage_abs.write_bytes(b"docx")
    record = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="bid.docx",
        file_type=FileType.docx,
        file_size=4,
        storage_path=storage_rel,
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(record)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=record.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="bid.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    bid_outline = BidOutline(
        kb_id=seeded_kb.kb_id,
        import_id=record.import_id,
        source_doc_id=document.document_id,
        outline_name="outline",
        created_by="admin",
    )
    db_session.add(bid_outline)
    db_session.flush()
    db_session.add(
        ActualBidParseTask(
            kb_id=seeded_kb.kb_id,
            import_id=record.import_id,
            document_id=document.document_id,
            bid_outline_id=bid_outline.bid_outline_id,
            status=ActualBidParseTaskStatus.ready,
            created_by="admin",
        )
    )
    db_session.commit()

    patch = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/actual-bid-parse/documents/{document.document_id}",
        headers={"X-Operator-Id": "admin"},
        json={
            "bid_project_name": "测试项目",
            "bid_customer_name": "测试客户",
            "product_category_ids": [],
        },
    )
    assert patch.status_code == 200
    patch_data = patch.json()["data"]
    assert patch_data["bid_project_name"] == "测试项目"
    assert patch_data["bid_customer_name"] == "测试客户"
    assert patch_data["bid_outline_id"] == str(bid_outline.bid_outline_id)

    db_session.expire_all()
    refreshed = db_session.get(Document, document.document_id)
    assert refreshed is not None
    assert refreshed.bid_project_name == "测试项目"
    assert refreshed.bid_customer_name == "测试客户"


def test_get_document_not_found(client, seeded_kb):
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/actual-bid-parse/documents/00000000-0000-0000-0000-000000000001",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_list_file_imports_includes_latest_parse_task_id(client, db_session, seeded_kb, sample_docx_path):
    record = _seed_confirmed_actual_bid_import_with_downstreams(
        db_session, seeded_kb, sample_docx_path
    )
    task = ActualBidParseTask(
        kb_id=seeded_kb.kb_id,
        import_id=record.import_id,
        status=ActualBidParseTaskStatus.ready,
        created_by="admin",
    )
    db_session.add(task)
    db_session.commit()

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    row = next(item for item in items if item["import_id"] == str(record.import_id))
    assert row["latest_parse_task_id"] == str(task.parse_task_id)
    assert row["parse_status"] == "parse_ready"
