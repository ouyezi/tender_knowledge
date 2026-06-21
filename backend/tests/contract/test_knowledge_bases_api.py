import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_create_and_list_kb(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-A"},
            headers={"X-Operator-Id": "admin"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["name"] == "KB-A"
        assert "trace_id" in body

        list_response = await client.get("/api/v1/kbs?status=active")
        assert list_response.status_code == 200
        assert len(list_response.json()["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_create_kb_includes_timestamps(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-Timestamp"},
            headers={"X-Operator-Id": "admin"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        assert "T" in data["created_at"]

        list_response = await client.get("/api/v1/kbs?status=active")
        item = list_response.json()["data"]["items"][0]
        assert item["created_at"] is not None

