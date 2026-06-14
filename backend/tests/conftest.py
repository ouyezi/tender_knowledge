import os
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.session import Base, get_db
from src.main import app
from src.models.knowledge_base import KBStatus, KnowledgeBase
from src.models.file_import import FileImport
from src.services.import_task_runner import run_post_upload
from src.models import (  # noqa: F401
    actual_bid_audit_log,
    actual_bid_parse_task,
    audit_log,
    bid_outline,
    bid_outline_node,
    bid_outline_structure_diff,
    candidate_knowledge,
    candidate_knowledge_stub,
    chapter_pattern,
    chapter_pattern_mining_task,
    chapter_taxonomy,
    classification_reference,
    document,
    document_parse_suggestion,
    document_tree_node,
    downstream_task_entry,
    file_import,
    file_purpose_suggestion,
    import_audit_log,
    import_task,
    kb_clone_log,
    knowledge_base,
    product_category,
    template,
    template_audit_log,
    template_chapter,
    template_library,
    template_material,
    template_parse_suggestion,
    template_parse_task,
    template_publish_snapshot,
    template_rule,
    template_structure_diff,
    template_variable,
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
