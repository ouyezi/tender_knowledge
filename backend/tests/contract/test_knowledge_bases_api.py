from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import sessionmaker

from src.db.session import Base, get_db
from src.main import app


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
async def test_clone_kb_writes_log(api_client, db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        source = await client.post(
            "/api/v1/kbs",
            json={"name": "source"},
            headers={"X-Operator-Id": "admin"},
        )
        source_id = source.json()["data"]["kb_id"]
        target = await client.post(
            "/api/v1/kbs",
            json={"name": "target", "clone_from_kb_id": source_id},
            headers={"X-Operator-Id": "admin"},
        )
        assert target.status_code == 200
        assert target.json()["data"]["kb_id"] != source_id

    from sqlalchemy import select

    from src.models.kb_clone_log import KBCloneLog

    log = db_session.scalar(
        select(KBCloneLog).where(
            KBCloneLog.source_kb_id == UUID(source_id),
        )
    )
    assert log is not None
