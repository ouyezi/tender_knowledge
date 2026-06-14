from e2e.steps.retrieval_extended import _build_search_body


def test_build_search_body_bm25_only():
    body = _build_search_body(query="技术方案", category_id=None, include_trace=False, vector=False)
    assert body["retrieval_options"]["enable_bm25"] is True
    assert body["retrieval_options"]["enable_vector"] is False
    assert "product_category_ids" not in body


def test_build_search_body_with_category_and_trace():
    body = _build_search_body(
        query="测试", category_id="cat-1", include_trace=True, vector=False
    )
    assert body["product_category_ids"] == ["cat-1"]
    assert body["return_options"]["include_trace"] is True
