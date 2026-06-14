import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / "scripts" / "lib"))
sys.path.insert(0, str(ROOT))

from e2e.client import IntegrationClient


def test_integration_client_health(client):
    api = IntegrationClient(client, operator_id="admin")
    resp = api.request("GET", "/health")
    assert resp.ok
    assert resp.json.get("status") == "ok"


def test_integration_client_kb_get(client, seeded_kb):
    api = IntegrationClient(client, operator_id="admin")
    resp = api.request("GET", f"/api/v1/kbs/{seeded_kb.kb_id}")
    assert resp.ok
