from uuid import UUID

from src.services.file_storage import FileStorage


def test_save_and_resolve_path(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    storage = FileStorage()
    kb_id = UUID("00000000-0000-0000-0000-000000000001")
    import_id = UUID("00000000-0000-0000-0000-000000000002")
    rel = storage.save(
        kb_id=kb_id,
        import_id=import_id,
        file_name="a.docx",
        stream=iter([b"hello"]),
    )
    assert rel == f"{kb_id}/{import_id}/a.docx"
    assert (tmp_path / rel).read_bytes() == b"hello"
