from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from src.config import Settings
from src.main import app
from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.bid_outline import BidOutline
from src.models.bid_outline_node import BidOutlineNode
from src.models.bid_outline_structure_diff import BidOutlineStructureDiff, BidOutlineStructureDiffStatus
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.downstream_task_entry import DownstreamTaskEntry, DownstreamTaskStatus, DownstreamTaskType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.actual_bid_parse_runner import enqueue_actual_bid_parse, run_actual_bid_parse_pending


def _seed_locked_outline_import(db_session, seeded_kb, sample_docx_path):
    storage_rel = f"{seeded_kb.kb_id}/locked-actual-bid.docx"
    storage_abs = Path(Settings().storage_root) / storage_rel
    storage_abs.parent.mkdir(parents=True, exist_ok=True)
    storage_abs.write_bytes(sample_docx_path.read_bytes())

    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="locked-actual-bid.docx",
        file_type=FileType.docx,
        file_size=storage_abs.stat().st_size,
        storage_path=storage_rel,
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="locked-actual-bid.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    outline = BidOutline(
        kb_id=seeded_kb.kb_id,
        source_doc_id=document.document_id,
        import_id=file_import.import_id,
        outline_name="已锁定目录",
        structure_locked_by="admin",
        structure_locked_at=datetime.now(timezone.utc),
        created_by="admin",
    )
    db_session.add(outline)
    db_session.flush()

    db_session.add(
        BidOutlineNode(
            kb_id=seeded_kb.kb_id,
            bid_outline_id=outline.bid_outline_id,
            parent_id=None,
            title="旧目录节点",
            level=1,
            sort_order=0,
            needs_manual_review=False,
        )
    )
    db_session.add(
        DownstreamTaskEntry(
            kb_id=seeded_kb.kb_id,
            import_id=file_import.import_id,
            task_type=DownstreamTaskType.bid_outline_extract,
            status=DownstreamTaskStatus.pending,
        )
    )
    db_session.add(
        DownstreamTaskEntry(
            kb_id=seeded_kb.kb_id,
            import_id=file_import.import_id,
            task_type=DownstreamTaskType.candidate_knowledge_generate,
            status=DownstreamTaskStatus.pending,
        )
    )
    db_session.commit()
    return file_import, outline


def test_force_reparse_locked_outline_generates_pending_diff_without_mutating_nodes(
    db_session, seeded_kb, sample_docx_path
):
    file_import, outline = _seed_locked_outline_import(db_session, seeded_kb, sample_docx_path)
    original_titles = [
        node.title
        for node in db_session.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == outline.bid_outline_id)
        .order_by(BidOutlineNode.sort_order.asc())
        .all()
    ]

    enqueue_actual_bid_parse(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        operator_id="admin",
        trace_id=None,
        force_reparse=True,
    )
    run_actual_bid_parse_pending(db_session)

    task = (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == file_import.import_id)
        .order_by(ActualBidParseTask.created_at.desc())
        .first()
    )
    assert task is not None
    diff = (
        db_session.query(BidOutlineStructureDiff)
        .filter(
            BidOutlineStructureDiff.bid_outline_id == outline.bid_outline_id,
            BidOutlineStructureDiff.parse_task_id == task.parse_task_id,
        )
        .one_or_none()
    )
    assert diff is not None
    assert diff.status == BidOutlineStructureDiffStatus.pending
    assert isinstance((diff.diff_payload or {}).get("suggested_tree"), list)
    refreshed_titles = [
        node.title
        for node in db_session.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == outline.bid_outline_id)
        .order_by(BidOutlineNode.sort_order.asc())
        .all()
    ]
    assert refreshed_titles == original_titles


def test_bid_outline_diff_apply_and_reject_endpoints(
    api_client, db_session, seeded_kb, sample_docx_path
):
    client = TestClient(app)
    file_import, outline = _seed_locked_outline_import(db_session, seeded_kb, sample_docx_path)

    enqueue_actual_bid_parse(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        operator_id="admin",
        trace_id=None,
        force_reparse=True,
    )
    run_actual_bid_parse_pending(db_session)
    task = (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == file_import.import_id)
        .order_by(ActualBidParseTask.created_at.desc())
        .first()
    )
    assert task is not None
    diff = (
        db_session.query(BidOutlineStructureDiff)
        .filter(BidOutlineStructureDiff.parse_task_id == task.parse_task_id)
        .one()
    )

    list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/diffs",
        headers={"X-Operator-Id": "admin"},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["data"]["items"][0]["status"] == "pending"

    apply_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/diffs/{diff.diff_id}/apply",
        headers={"X-Operator-Id": "admin"},
    )
    assert apply_resp.status_code == 200
    assert apply_resp.json()["data"]["structure_diff"]["status"] == "applied"

    enqueue_actual_bid_parse(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        operator_id="admin",
        trace_id=None,
        force_reparse=True,
    )
    run_actual_bid_parse_pending(db_session)
    new_task = (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == file_import.import_id)
        .order_by(ActualBidParseTask.created_at.desc())
        .first()
    )
    new_diff = (
        db_session.query(BidOutlineStructureDiff)
        .filter(
            BidOutlineStructureDiff.parse_task_id == new_task.parse_task_id,
            BidOutlineStructureDiff.status == BidOutlineStructureDiffStatus.pending,
        )
        .one()
    )
    reject_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/diffs/{new_diff.diff_id}/reject",
        headers={"X-Operator-Id": "admin"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["data"]["structure_diff"]["status"] == "rejected"
