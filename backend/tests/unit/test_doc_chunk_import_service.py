from pathlib import Path
from uuid import uuid4

from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.doc_chunk.import_service import import_workspace_for_knowledge_entry

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_import_workspace_for_knowledge_entry_actual_bid(db_session, seeded_kb):
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

    result = import_workspace_for_knowledge_entry(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        workspace=FIXTURE_ROOT,
        file_import=file_import,
    )
    assert result.parse_engine == "doc_chunk"
    assert result.tree_node_count >= 1
    assert result.document_id is not None

    from src.models.document import Document, DocumentParseStatus, DocumentSourceType

    document = db_session.get(Document, result.document_id)
    assert document is not None
    assert document.source_type == DocumentSourceType.actual_bid
    assert document.parse_status == DocumentParseStatus.ready


def test_import_workspace_for_knowledge_entry_template_file(db_session, seeded_kb):
    import_id = uuid4()
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="template.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="x/template.docx",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    result = import_workspace_for_knowledge_entry(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        workspace=FIXTURE_ROOT,
        file_import=file_import,
    )
    assert result.parse_engine == "doc_chunk"
    assert result.tree_node_count >= 1

    from src.models.document import Document, DocumentSourceType

    document = db_session.get(Document, result.document_id)
    assert document.source_type == DocumentSourceType.template_file
