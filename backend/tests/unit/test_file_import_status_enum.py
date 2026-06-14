from src.models.file_import import FileImportStatus


def test_file_import_status_has_deleted():
    assert FileImportStatus.deleted.value == "deleted"
