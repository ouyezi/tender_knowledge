from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.downstream_task_entry import (
    DownstreamTaskEntry,
    DownstreamTaskStatus,
    DownstreamTaskType,
)
from src.models.file_import import (
    FileImport,
    FileImportStatus,
    FilePurpose,
    FileType,
    HashStatus,
)
from src.services.confirm_service import _downstream_task_types
from src.models.file_import import FilePurpose as FP
from src.services.document_parse_runner import (
    DocumentParseServiceError,
    _parse_task_id_from_entry,
    enqueue_document_parse,
    run_document_parse_once,
)


def test_downstream_task_types_only_document_parse():
    assert _downstream_task_types(FP.actual_bid, True) == [
        DownstreamTaskType.document_parse
    ]
    assert _downstream_task_types(FP.template_file, True) == [
        DownstreamTaskType.document_parse
    ]
    assert _downstream_task_types(FP.actual_bid, False) == []


def test_document_parse_runner_exports():
    from src.services import document_parse_runner

    assert callable(document_parse_runner.enqueue_document_parse)
    assert callable(document_parse_runner.run_document_parse_in_new_session)
    assert callable(document_parse_runner.run_document_parse_once)


def test_parse_task_id_from_entry_requires_parse_task_id():
    entry = DownstreamTaskEntry(
        kb_id=uuid4(),
        import_id=uuid4(),
        task_type=DownstreamTaskType.document_parse,
        payload={"file_purpose": "actual_bid"},
    )
    assert _parse_task_id_from_entry(entry) is None


def test_enqueue_document_parse_allows_force_reparse_for_completed_import(db_session: Session):
    kb_id = uuid4()
    import_id = uuid4()
    file_import = FileImport(
        kb_id=kb_id,
        import_id=import_id,
        file_name="sample.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{kb_id}/{import_id}/sample.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(file_import)
    db_session.commit()

    task = enqueue_document_parse(
        db_session,
        kb_id=kb_id,
        import_id=import_id,
        operator_id="tester",
        trace_id=None,
        force_reparse=True,
    )

    db_session.refresh(file_import)
    assert file_import.status == FileImportStatus.confirmed
    assert task.status == ActualBidParseTaskStatus.pending


def test_enqueue_document_parse_rejects_completed_import_without_force_reparse(db_session: Session):
    kb_id = uuid4()
    import_id = uuid4()
    file_import = FileImport(
        kb_id=kb_id,
        import_id=import_id,
        file_name="sample.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{kb_id}/{import_id}/sample.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(file_import)
    db_session.commit()

    with pytest.raises(DocumentParseServiceError) as exc:
        enqueue_document_parse(
            db_session,
            kb_id=kb_id,
            import_id=import_id,
            operator_id="tester",
            trace_id=None,
            force_reparse=False,
        )

    assert exc.value.code == "IMPORT_NOT_CONFIRMED"


def test_run_document_parse_once_fails_legacy_entry_without_blocking_queue(db_session: Session):
    kb_id = uuid4()
    import_id = uuid4()
    parse_task_id = uuid4()

    file_import = FileImport(
        kb_id=kb_id,
        import_id=import_id,
        file_name="sample.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{kb_id}/{import_id}/sample.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    legacy_entry = DownstreamTaskEntry(
        kb_id=kb_id,
        import_id=import_id,
        task_type=DownstreamTaskType.document_parse,
        status=DownstreamTaskStatus.pending,
        payload={"file_purpose": "actual_bid"},
    )
    valid_entry = DownstreamTaskEntry(
        kb_id=kb_id,
        import_id=import_id,
        task_type=DownstreamTaskType.document_parse,
        status=DownstreamTaskStatus.pending,
        payload={"parse_task_id": str(parse_task_id)},
    )
    parse_task = ActualBidParseTask(
        parse_task_id=parse_task_id,
        kb_id=kb_id,
        import_id=import_id,
        status=ActualBidParseTaskStatus.pending,
        created_by="tester",
    )
    db_session.add_all([file_import, legacy_entry, valid_entry, parse_task])
    db_session.commit()

    assert run_document_parse_once(db_session) is True
    db_session.refresh(legacy_entry)
    assert legacy_entry.status == DownstreamTaskStatus.failed

    # Second run should pick up the valid entry (will fail on missing file, but not block queue).
    with pytest.raises(FileNotFoundError):
        run_document_parse_once(db_session)
