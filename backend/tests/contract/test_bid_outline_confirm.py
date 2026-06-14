from src.models.actual_bid_audit_log import ActualBidAuditLog
from src.models.bid_outline import BidOutline, BidOutlineStatus
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType


def _seed_draft_outline(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="confirm-outline.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{seeded_kb.kb_id}/confirm-outline.docx",
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
        document_name="confirm-outline.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    outline = BidOutline(
        kb_id=seeded_kb.kb_id,
        source_doc_id=document.document_id,
        import_id=file_import.import_id,
        outline_name="待确认目录",
        created_by="admin",
    )
    db_session.add(outline)
    db_session.commit()
    db_session.refresh(outline)
    return outline


def test_confirm_outline_sets_structure_locked(client, db_session, seeded_kb):
    outline = _seed_draft_outline(db_session, seeded_kb)

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/bid-outlines/{outline.bid_outline_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={"status": "confirmed"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["structure_locked_at"] is not None
    assert data["status"] == "confirmed"
    assert data["bid_outline_id"] == str(outline.bid_outline_id)

    db_session.expire_all()
    refreshed = db_session.get(BidOutline, outline.bid_outline_id)
    assert refreshed is not None
    assert refreshed.status == BidOutlineStatus.confirmed
    assert refreshed.structure_locked_at is not None
    assert refreshed.structure_locked_by == "admin"

    audit = (
        db_session.query(ActualBidAuditLog)
        .filter(
            ActualBidAuditLog.kb_id == seeded_kb.kb_id,
            ActualBidAuditLog.object_id == outline.bid_outline_id,
            ActualBidAuditLog.action == "outline_confirmed",
        )
        .one_or_none()
    )
    assert audit is not None
    assert audit.object_type == "bid_outline"
    assert audit.operator_id == "admin"
