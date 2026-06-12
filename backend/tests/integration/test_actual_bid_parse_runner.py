from pathlib import Path

from src.config import Settings
from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.bid_outline import BidOutline
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.document import Document
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
    return record.import_id


def test_actual_bid_parse_runner_creates_parse_outputs(db_session, seeded_kb):
    sample_docx_path = Path(__file__).resolve().parent.parent / "fixtures" / "sample-actual-bid.docx"
    import_id = _seed_confirmed_actual_bid_import_with_downstreams(
        db_session, seeded_kb, sample_docx_path
    )

    run_actual_bid_parse_pending(db_session)

    task = (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == import_id)
        .order_by(ActualBidParseTask.created_at.desc())
        .first()
    )
    assert task is not None
    assert task.status == ActualBidParseTaskStatus.ready
    assert task.document_id is not None
    assert task.bid_outline_id is not None

    document = db_session.get(Document, task.document_id)
    assert document is not None

    bid_outline = db_session.get(BidOutline, task.bid_outline_id)
    assert bid_outline is not None

    candidate_count = (
        db_session.query(CandidateKnowledge)
        .filter(
            CandidateKnowledge.import_id == import_id,
            CandidateKnowledge.source_doc_id == task.document_id,
            CandidateKnowledge.parse_task_id == task.parse_task_id,
        )
        .count()
    )
    assert candidate_count >= 0

    downstream_entries = (
        db_session.query(DownstreamTaskEntry)
        .filter(DownstreamTaskEntry.import_id == import_id)
        .all()
    )
    assert len(downstream_entries) == 3
    assert {entry.status for entry in downstream_entries} == {DownstreamTaskStatus.completed}
