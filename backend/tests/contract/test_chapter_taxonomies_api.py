import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_chapter_taxonomy_synonyms_binding_and_filter(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-chapter"},
            headers={"X-Operator-Id": "admin"},
        )
        kb_id = kb.json()["data"]["kb_id"]

        category = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={
                "category_name": "福利产品",
                "category_code": "welfare",
                "aliases": [],
            },
            headers={"X-Operator-Id": "admin"},
        )
        category_id = category.json()["data"]["category_id"]

        created = await client.post(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies",
            json={
                "standard_name": "售后服务方案",
                "taxonomy_code": "after-sales",
                "synonyms": ["驻场服务方案"],
                "product_category_ids": [category_id],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert created.status_code == 200
        taxonomy_id = created.json()["data"]["taxonomy_id"]
        assert created.json()["data"]["synonyms"] == ["驻场服务方案"]

        synonyms = await client.put(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies/{taxonomy_id}/synonyms",
            json={"synonyms": ["驻场服务方案", "服务保障方案"]},
            headers={"X-Operator-Id": "admin"},
        )
        assert synonyms.status_code == 200
        assert set(synonyms.json()["data"]["synonyms"]) == {
            "驻场服务方案",
            "服务保障方案",
        }

        bindings = await client.put(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies/{taxonomy_id}/product-categories",
            json={"product_category_ids": [category_id], "source": "manual"},
            headers={"X-Operator-Id": "admin"},
        )
        assert bindings.status_code == 200
        assert bindings.json()["data"]["product_category_ids"] == [category_id]

        filtered = await client.get(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies",
            params={"product_category_id": category_id},
        )
        assert filtered.status_code == 200
        items = filtered.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["taxonomy_id"] == taxonomy_id

        unbound = await client.post(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies",
            json={
                "standard_name": "技术方案",
                "taxonomy_code": "tech",
                "synonyms": [],
                "product_category_ids": [],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert unbound.status_code == 200

        filtered_again = await client.get(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies",
            params={"product_category_id": category_id},
        )
        assert len(filtered_again.json()["data"]["items"]) == 1


@pytest.mark.asyncio
async def test_chapter_taxonomy_tree(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-tree"},
            headers={"X-Operator-Id": "admin"},
        )
        kb_id = kb.json()["data"]["kb_id"]

        root = await client.post(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies",
            json={
                "standard_name": "投标章节",
                "taxonomy_code": "bid",
                "synonyms": [],
            },
            headers={"X-Operator-Id": "admin"},
        )
        root_id = root.json()["data"]["taxonomy_id"]

        child = await client.post(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies",
            json={
                "parent_id": root_id,
                "standard_name": "售后服务方案",
                "taxonomy_code": "after-sales",
                "synonyms": ["服务保障"],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert child.status_code == 200

        tree = await client.get(f"/api/v1/kbs/{kb_id}/chapter-taxonomies/tree")
        assert tree.status_code == 200
        nodes = tree.json()["data"]["nodes"]
        assert len(nodes) == 1
        assert len(nodes[0]["children"]) == 1
        assert nodes[0]["children"][0]["standard_name"] == "售后服务方案"


@pytest.mark.asyncio
async def test_synonym_conflict_returns_409(api_client):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-syn-conflict"},
            headers={"X-Operator-Id": "admin"},
        )
        kb_id = kb.json()["data"]["kb_id"]

        first = await client.post(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies",
            json={
                "standard_name": "售后服务方案",
                "taxonomy_code": "after-sales",
                "synonyms": ["驻场服务"],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert first.status_code == 200

        second = await client.post(
            f"/api/v1/kbs/{kb_id}/chapter-taxonomies",
            json={
                "standard_name": "其他章节",
                "taxonomy_code": "other",
                "synonyms": ["驻场服务"],
            },
            headers={"X-Operator-Id": "admin"},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "CONFLICT"
