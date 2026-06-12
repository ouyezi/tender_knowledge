from uuid import uuid4

from src.models.actual_bid_parse_task import (
    ActualBidParseTask,
    ActualBidParseTaskStatus,
)
from src.models.document import Document, DocumentSourceType, DocumentParseStatus


def test_create_document_and_parse_task(db_session):
    kb_id = uuid4()
    import_id = uuid4()
    doc = Document(
        kb_id=kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="某项目投标书.docx",
        parse_status=DocumentParseStatus.pending,
        created_by="admin",
    )
    db_session.add(doc)
    db_session.flush()
    task = ActualBidParseTask(
        kb_id=kb_id,
        import_id=import_id,
        document_id=doc.document_id,
        status=ActualBidParseTaskStatus.pending,
        trace_id=uuid4(),
        created_by="admin",
    )
    db_session.add(task)
    db_session.commit()
    assert doc.document_id is not None
    assert task.parse_task_id is not None
