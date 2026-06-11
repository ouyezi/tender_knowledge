from uuid import uuid4

from src.models.file_import import FileImport, FileImportStatus, FileType


def test_create_file_import(db_session):
    kb_id = uuid4()
    imp = FileImport(
        kb_id=kb_id,
        file_name="t.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="x/y/t.docx",
        status=FileImportStatus.uploaded,
        created_by="admin",
    )
    db_session.add(imp)
    db_session.commit()
    assert imp.import_id is not None
