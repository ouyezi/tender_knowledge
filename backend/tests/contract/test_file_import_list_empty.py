from fastapi.testclient import TestClient

from src.main import app
from src.models.knowledge_base import KnowledgeBase, KBStatus


def test_list_file_imports_empty(api_client, db_session):
    kb = KnowledgeBase(name="test-kb", status=KBStatus.active)
    db_session.add(kb)
    db_session.commit()
    client = TestClient(app)
    r = client.get(
        f"/api/v1/kbs/{kb.kb_id}/file-imports",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["items"] == []
    assert body["data"]["total"] == 0
