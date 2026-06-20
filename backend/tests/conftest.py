import os
import sys
from pathlib import Path
from uuid import UUID

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.session import Base, get_db
from src.main import app
from src.models.knowledge_base import KBStatus, KnowledgeBase
from src.models.file_import import FileImport
from src.models.file_import import FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.import_task_runner import run_post_upload
from src.models import (  # noqa: F401
    actual_bid_parse_task,
    chunk_asset,
    chunk_embedding,
    document,
    document_media_asset,
    document_parse_suggestion,
    document_tree_node,
    downstream_task_entry,
    file_import,
    file_purpose_suggestion,
    import_audit_log,
    import_task,
    kb_clone_log,
    knowledge_base,
    knowledge_chunk,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite://")


@pytest.fixture()
def db_engine():
    sqlite_kwargs = {}
    if TEST_DATABASE_URL.startswith("sqlite"):
        sqlite_kwargs = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    engine = create_engine(TEST_DATABASE_URL, **sqlite_kwargs)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client(db_engine):
    Base.metadata.create_all(bind=db_engine)
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def client(api_client):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def seeded_kb(db_session):
    kb = KnowledgeBase(name="seeded-kb", status=KBStatus.active)
    db_session.add(kb)
    db_session.commit()
    db_session.refresh(kb)
    return kb


@pytest.fixture()
def sample_docx_path() -> Path:
    actual = Path(__file__).parent / "fixtures" / "sample-actual-bid.docx"
    if actual.exists():
        return actual
    return Path(__file__).parent / "fixtures" / "sample-template.docx"


@pytest.fixture(autouse=True)
def storage_root_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))


@pytest.fixture()
def uploaded_need_confirm(client, seeded_kb, sample_docx_path, db_session):
    with sample_docx_path.open("rb") as f:
        resp = client.post(
            f"/api/v1/kbs/{seeded_kb.kb_id}/file-imports",
            headers={"X-Operator-Id": "admin"},
            files={
                "file": (
                    "餐补模板.docx",
                    f,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert resp.status_code == 201
    import_id = UUID(resp.json()["data"]["import_id"])
    run_post_upload(db_session, import_id)
    record = db_session.get(FileImport, import_id)
    assert record is not None
    assert record.status.value == "need_confirm"
    return {"kb_id": seeded_kb.kb_id, "import_id": import_id}


def _seed_file_import(db_session, kb_id, *, name: str) -> FileImport:
    item = FileImport(
        kb_id=kb_id,
        file_name=name,
        file_type=FileType.docx,
        file_size=1024,
        storage_path=f"/tmp/{name}",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(item)
    db_session.flush()
    return item
