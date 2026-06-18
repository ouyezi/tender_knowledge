from uuid import uuid4

from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.actual_bid_parse_runner import enqueue_actual_bid_parse


def test_force_reparse_resets_claimed_document_parse_entry(db_session, seeded_kb):
    record = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="stuck.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path=f"{seeded_kb.kb_id}/stuck.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    db_session.add(record)
    db_session.flush()

    stale_task = ActualBidParseTask(
        kb_id=seeded_kb.kb_id,
        import_id=record.import_id,
        status=ActualBidParseTaskStatus.running,
        created_by="admin",
    )
    claimed_entry = DownstreamTaskEntry(
        kb_id=seeded_kb.kb_id,
        import_id=record.import_id,
        task_type=DownstreamTaskType.document_parse,
        status=DownstreamTaskStatus.claimed,
        claimed_by="actual_bid_parse_runner",
        payload={"parse_task_id": str(uuid4())},
    )
    db_session.add_all([stale_task, claimed_entry])
    db_session.commit()

    new_task = enqueue_actual_bid_parse(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=record.import_id,
        operator_id="admin",
        trace_id=None,
        force_reparse=True,
    )

    db_session.refresh(stale_task)
    db_session.refresh(claimed_entry)
    assert stale_task.status == ActualBidParseTaskStatus.failed
    assert claimed_entry.status == DownstreamTaskStatus.pending
    assert claimed_entry.claimed_by is None
    assert claimed_entry.payload["parse_task_id"] == str(new_task.parse_task_id)
    assert new_task.status == ActualBidParseTaskStatus.pending
