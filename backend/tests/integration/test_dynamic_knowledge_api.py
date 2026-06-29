from __future__ import annotations


def test_dynamic_knowledge_crud(client, seeded_kb, seeded_taxonomy):
    _ = seeded_taxonomy
    create = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/dynamic-knowledge",
        json={
            "dynamic_type_code": "brand_authorization",
            "title": "品牌授权-A",
            "content": "授权内容",
            "structured_data": {"brand": "测试品牌"},
            "business_line_codes": ["general"],
            "status": "active",
        },
    )
    assert create.status_code == 201
    record_id = create.json()["data"]["id"]

    detail = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/dynamic-knowledge/{record_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["dynamic_type_label"] == "品牌授权信息"

    update = client.put(
        f"/api/v1/kbs/{seeded_kb.kb_id}/dynamic-knowledge/{record_id}",
        json={"business_line_codes": ["insurance"], "title": "品牌授权-B"},
    )
    assert update.status_code == 200
    assert update.json()["data"]["business_line_labels"] == ["保险"]
    assert update.json()["data"]["title"] == "品牌授权-B"

    listing = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/dynamic-knowledge",
        params={"dynamic_type_code": "brand_authorization"},
    )
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1

    deleted = client.delete(f"/api/v1/kbs/{seeded_kb.kb_id}/dynamic-knowledge/{record_id}")
    assert deleted.status_code == 200
    gone = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/dynamic-knowledge/{record_id}")
    assert gone.status_code == 404
