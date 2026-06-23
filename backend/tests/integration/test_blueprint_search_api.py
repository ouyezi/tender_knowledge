from __future__ import annotations

MOCK_PARSE_JSON = {
    "semantic_query": "政务云 架构",
    "keyword": "政务云",
    "product_tags": ["政务云"],
    "industry_tags": [],
    "scenario_tags": [],
}


def test_parse_search_query_api(client, seeded_kb, monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.blueprints.parse_search_query",
        lambda **_: MOCK_PARSE_JSON,
    )
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/parse-search-query",
        json={"query": "找政务云架构蓝图"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["keyword"] == "政务云"


def test_search_api_requires_query(client, seeded_kb):
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/search",
        json={"semantic_query": "", "keyword": ""},
    )
    assert resp.status_code == 400
