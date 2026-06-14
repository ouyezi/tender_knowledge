import os
from pathlib import Path
from uuid import UUID
from uuid import uuid4

import pytest
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
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.models import (  # noqa: F401
    actual_bid_audit_log,
    actual_bid_parse_task,
    audit_log,
    bid_outline,
    bid_outline_node,
    bid_outline_structure_diff,
    candidate_confirm_audit_log,
    candidate_knowledge,
    candidate_knowledge_stub,
    chapter_draft,
    chapter_pattern,
    chapter_pattern_mining_task,
    chapter_taxonomy,
    classification_reference,
    document,
    document_media_asset,
    document_parse_suggestion,
    document_tree_node,
    downstream_task_entry,
    file_import,
    file_purpose_suggestion,
    generation_snapshot,
    generation_task,
    import_audit_log,
    import_task,
    kb_clone_log,
    knowledge_base,
    knowledge_unit,
    manual_asset,
    module_assembly_suggestion,
    product_category,
    prompt_config_version,
    retrieval_eval_case,
    retrieval_eval_run,
    retrieval_eval_set,
    retrieval_feedback,
    retrieval_index_entry,
    retrieval_strategy_version,
    retrieval_trace,
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
    tender_requirement_context,
    wiki,
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


@pytest.fixture()
def epic6_generation_seed(client, seeded_kb, db_session):
    category_id = str(uuid4())
    template_import = _seed_file_import(db_session, seeded_kb.kb_id, name="epic6-template.docx")
    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=template_import.import_id,
        template_name="Epic6 模板",
        template_type=TemplateType.technical_bid,
        product_category_ids=[category_id],
        status=TemplateStatus.published,
        created_by="tester",
    )
    db_session.add(template)
    db_session.flush()

    chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="技术方案",
        level=1,
        sort_order=0,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add(chapter)
    db_session.commit()

    tender_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/tender-requirements",
        json={
            "title": "Epic6 快速流转",
            "outline_nodes": [{"title": "技术方案", "level": 1, "sort_order": 0}],
            "score_points": [{"node_ref": "1", "text": "总体架构能力"}],
            "rejection_clauses": ["禁止要求原厂授权"],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert tender_resp.status_code == 200
    requirement_context_id = tender_resp.json()["data"]["requirement_context_id"]

    suggestion_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions",
        json={
            "product_category_ids": [category_id],
            "requirement_context_id": requirement_context_id,
            "outline_nodes": [{"title": "技术方案", "level": 1, "sort_order": 0}],
            "tender_requirement_context": {
                "rejection_clauses": ["禁止要求原厂授权"],
                "score_points": ["总体架构能力"],
            },
            "retrieval_options": {"top_k": 10},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert suggestion_resp.status_code == 200
    suggestion_id = suggestion_resp.json()["data"]["module_suggestions"][0]["suggestion_id"]

    adopt_resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions/{suggestion_id}/adoption",
        json={"status": "adopted", "adoption_reason": "测试采纳"},
        headers={"X-Operator-Id": "tester"},
    )
    assert adopt_resp.status_code == 200

    return {
        "kb_id": str(seeded_kb.kb_id),
        "category_id": category_id,
        "requirement_context_id": requirement_context_id,
        "suggestion_id": suggestion_id,
    }
