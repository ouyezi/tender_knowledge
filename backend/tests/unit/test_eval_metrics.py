from src.services.retrieval.eval.metrics import compute_metrics


def test_compute_metrics_with_hits():
    metrics = compute_metrics(
        expected_object_ids=["A", "B"],
        predicted_object_ids=["X", "A", "B"],
        k=2,
    )
    assert metrics["recall_at_k"] == 0.5
    assert metrics["precision_at_k"] == 0.5
    assert metrics["mrr"] == 0.5
    assert metrics["ndcg"] > 0


def test_compute_metrics_without_expected_returns_zero():
    metrics = compute_metrics(
        expected_object_ids=[],
        predicted_object_ids=["X", "Y"],
        k=5,
    )
    assert metrics["recall_at_k"] == 0.0
    assert metrics["precision_at_k"] == 0.0
    assert metrics["mrr"] == 0.0
    assert metrics["ndcg"] == 0.0
