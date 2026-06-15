"""Integration coverage for doc_chunk parse path (fixture-injected pipeline)."""

from pathlib import Path

from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.document import Document
from src.models.downstream_task_entry import DownstreamTaskEntry, DownstreamTaskStatus, DownstreamTaskType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.actual_bid_parse_runner import enqueue_actual_bid_parse, run_actual_bid_parse_pending

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def _fake_pipeline(docx_path, workspace, **kwargs):
    import shutil

    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(FIXTURE_ROOT, workspace)


def test_doc_chunk_parse_flow_produces_candidates(db_session, seeded_kb, sample_docx_path, monkeypatch):
    from src.config import Settings

    monkeypatch.setenv("USE_DOC_CHUNK_PARSE", "true")
    monkeypatch.setattr(
        "src.services.actual_bid_parse_runner.run_doc_chunk_pipeline",
        _fake_pipeline,
    )

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
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    db_session.add(record)
    db_session.flush()
    db_session.add(
        DownstreamTaskEntry(
            kb_id=seeded_kb.kb_id,
            import_id=record.import_id,
            task_type=DownstreamTaskType.document_parse,
            status=DownstreamTaskStatus.pending,
        )
    )
    db_session.commit()

    enqueue_actual_bid_parse(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=record.import_id,
        operator_id="admin",
        trace_id=None,
    )
    run_actual_bid_parse_pending(db_session)

    task = (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == record.import_id)
        .one()
    )
    assert task.status == ActualBidParseTaskStatus.ready
    document = db_session.get(Document, task.document_id)
    assert document is not None
    candidate_count = (
        db_session.query(CandidateKnowledge)
        .filter(CandidateKnowledge.source_doc_id == document.document_id)
        .count()
    )
    assert candidate_count == 2
