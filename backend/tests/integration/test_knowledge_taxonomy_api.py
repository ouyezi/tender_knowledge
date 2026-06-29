from __future__ import annotations


def test_list_taxonomy_block_type(client, seeded_taxonomy):
    _ = seeded_taxonomy
    resp = client.get("/api/v1/knowledge-taxonomy", params={"dimension": "block_type"})
    assert resp.status_code == 200
    body = resp.json()
    codes = {item["code"] for item in body["data"]["items"]}
    assert "qualification_document" in codes
    assert "qualification_sub_brand" in codes


def test_get_taxonomy_item_by_code(client, seeded_taxonomy):
    _ = seeded_taxonomy
    resp = client.get("/api/v1/knowledge-taxonomy/product_solution")
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["code"] == "product_solution"
    assert payload["label"] == "产品方案知识"


def test_get_taxonomy_item_not_found(client, seeded_taxonomy):
    _ = seeded_taxonomy
    resp = client.get("/api/v1/knowledge-taxonomy/not-real")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
