import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_create_three_level_tree(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post(
            "/api/v1/kbs",
            json={"name": "KB"},
            headers={"X-Operator-Id": "admin"},
        )
        kb_id = kb.json()["data"]["kb_id"]

        root = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={
                "category_name": "福利产品",
                "category_code": "welfare",
                "aliases": [],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert root.status_code == 200
        root_id = root.json()["data"]["category_id"]

        child = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={
                "parent_id": root_id,
                "category_name": "餐补",
                "category_code": "meal",
                "aliases": ["员工餐补"],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert child.status_code == 200

        tree = await client.get(f"/api/v1/kbs/{kb_id}/product-categories/tree")
        assert tree.status_code == 200
        nodes = tree.json()["data"]["nodes"]
        assert len(nodes) == 1
        assert len(nodes[0]["children"]) == 1
        assert nodes[0]["children"][0]["category_name"] == "餐补"


@pytest.mark.asyncio
async def test_alias_conflict_returns_409(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-conflict"},
            headers={"X-Operator-Id": "admin"},
        )
        kb_id = kb.json()["data"]["kb_id"]

        first = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={
                "category_name": "福利产品",
                "category_code": "welfare",
                "aliases": ["员工餐补"],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert first.status_code == 200

        second = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={
                "category_name": "其他",
                "category_code": "other",
                "aliases": ["员工餐补"],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert second.status_code == 409
        body = second.json()
        assert body["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_put_aliases_and_search(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-search"},
            headers={"X-Operator-Id": "admin"},
        )
        kb_id = kb.json()["data"]["kb_id"]

        created = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={
                "category_name": "福利产品",
                "category_code": "welfare",
                "aliases": [],
            },
            headers={"X-Operator-Id": "admin"},
        )
        category_id = created.json()["data"]["category_id"]

        updated = await client.put(
            f"/api/v1/kbs/{kb_id}/product-categories/{category_id}/aliases",
            json={"aliases": ["员工福利", "企业福利"]},
            headers={"X-Operator-Id": "admin"},
        )
        assert updated.status_code == 200
        assert set(updated.json()["data"]["aliases"]) == {"员工福利", "企业福利"}

        search = await client.get(
            f"/api/v1/kbs/{kb_id}/product-categories/search",
            params={"q": "员工福利"},
        )
        assert search.status_code == 200
        items = search.json()["data"]["items"]
        assert len(items) >= 1
        assert items[0]["category_name"] == "福利产品"


@pytest.mark.asyncio
async def test_create_category_when_alias_matches_name(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-alias-dedupe"},
            headers={"X-Operator-Id": "admin"},
        )
        kb_id = kb.json()["data"]["kb_id"]

        response = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={
                "category_name": "资质",
                "category_code": "zizhi",
                "description": "资质",
                "aliases": ["资质", "公司资质"],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["category_name"] == "资质"
        assert data["aliases"] == ["公司资质"]


@pytest.mark.asyncio
async def test_impact_and_merge(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-lifecycle"},
            headers={"X-Operator-Id": "admin"},
        )
        kb_id = kb.json()["data"]["kb_id"]

        source = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={"category_name": "源分类", "category_code": "source"},
            headers={"X-Operator-Id": "admin"},
        )
        source_id = source.json()["data"]["category_id"]
        target = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={"category_name": "目标分类", "category_code": "target"},
            headers={"X-Operator-Id": "admin"},
        )
        target_id = target.json()["data"]["category_id"]

        impact = await client.get(
            f"/api/v1/kbs/{kb_id}/product-categories/{source_id}/impact"
        )
        assert impact.status_code == 200
        assert impact.json()["data"]["total_count"] == 0

        merged = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories/{source_id}/merge",
            json={"target_category_id": target_id},
            headers={"X-Operator-Id": "admin"},
        )
        assert merged.status_code == 200
        assert merged.json()["data"]["target_id"] == target_id
