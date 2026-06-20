from uuid import UUID, uuid4

from src.models.downstream_task_entry import DownstreamTaskType
from src.services.confirm_service import _downstream_task_types
from src.models.file_import import FilePurpose


def test_downstream_task_types_only_document_parse():
    assert _downstream_task_types(FilePurpose.actual_bid, True) == [
        DownstreamTaskType.document_parse
    ]
    assert _downstream_task_types(FilePurpose.template_file, True) == [
        DownstreamTaskType.document_parse
    ]
    assert _downstream_task_types(FilePurpose.actual_bid, False) == []


def test_document_parse_runner_exports():
    from src.services import document_parse_runner

    assert callable(document_parse_runner.enqueue_document_parse)
    assert callable(document_parse_runner.run_document_parse_in_new_session)
    assert callable(document_parse_runner.run_document_parse_once)
