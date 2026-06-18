from pathlib import Path
from uuid import uuid4

from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.doc_chunk.import_service import import_workspace

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_import_workspace_orchestration(db_session, seeded_kb):
    import_id = uuid4()
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="minimal.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="x/minimal.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()
    task = ActualBidParseTask(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        status=ActualBidParseTaskStatus.running,
        created_by="admin",
    )
    db_session.add(task)
    db_session.flush()

    result = import_workspace(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        document_id=None,
        parse_task_id=task.parse_task_id,
        workspace=FIXTURE_ROOT,
        file_import=file_import,
        task=task,
    )
    assert result.parse_engine == "doc_chunk"
    # 4 tree nodes from fixture + 4 enriched body nodes under t0001 heading (markdown slice)
    assert result.tree_node_count == 8
    assert result.outline_node_count == 2
    assert result.candidate_count == 2
