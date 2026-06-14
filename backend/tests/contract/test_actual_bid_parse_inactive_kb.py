from fastapi.testclient import TestClient

from src.main import app
from src.models.knowledge_base import KnowledgeBase, KBStatus


def test_trigger_parse_inactive_kb_forbidden(api_client, db_session):
    kb = KnowledgeBase(name="inactive-kb", status=KBStatus.inactive)
    db_session.add(kb)
    db_session.commit()
    client = TestClient(app)
    r = client.post(
        f"/api/v1/kbs/{kb.kb_id}/actual-bid-parse/trigger",
        headers={"X-Operator-Id": "admin"},
        json={"import_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 403
