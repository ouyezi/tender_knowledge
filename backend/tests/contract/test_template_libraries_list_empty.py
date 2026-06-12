from fastapi.testclient import TestClient

from src.main import app
from src.models.knowledge_base import KnowledgeBase, KBStatus


def test_list_template_libraries_empty(api_client, db_session):
    kb = KnowledgeBase(name="test-kb", status=KBStatus.active)
    db_session.add(kb)
    db_session.commit()
    client = TestClient(app)
    r = client.get(
        f"/api/v1/kbs/{kb.kb_id}/template-libraries",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []


def test_list_parse_tasks_empty(api_client, db_session):
    kb = KnowledgeBase(name="test-kb-2", status=KBStatus.active)
    db_session.add(kb)
    db_session.commit()
    client = TestClient(app)
    r = client.get(
        f"/api/v1/kbs/{kb.kb_id}/template-parse/tasks",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []
