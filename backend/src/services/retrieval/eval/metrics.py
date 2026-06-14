from __future__ import annotations

import math


def recall_at_k(expected_object_ids: list[str], predicted_object_ids: list[str], k: int) -> float:
    expected = set(expected_object_ids or [])
    if not expected:
        return 0.0
    topk = set((predicted_object_ids or [])[: max(1, k)])
    return round(len(expected.intersection(topk)) / len(expected), 4)


def precision_at_k(expected_object_ids: list[str], predicted_object_ids: list[str], k: int) -> float:
    top = (predicted_object_ids or [])[: max(1, k)]
    if not top:
        return 0.0
    expected = set(expected_object_ids or [])
    return round(len(expected.intersection(set(top))) / len(top), 4)


def mrr(expected_object_ids: list[str], predicted_object_ids: list[str], k: int) -> float:
    expected = set(expected_object_ids or [])
    if not expected:
        return 0.0
    top = (predicted_object_ids or [])[: max(1, k)]
    for idx, object_id in enumerate(top):
        if object_id in expected:
            return round(1.0 / (idx + 1), 4)
    return 0.0


def ndcg(expected_object_ids: list[str], predicted_object_ids: list[str], k: int) -> float:
    expected = set(expected_object_ids or [])
    if not expected:
        return 0.0
    top = (predicted_object_ids or [])[: max(1, k)]
    dcg = 0.0
    for idx, object_id in enumerate(top):
        if object_id in expected:
            dcg += 1.0 / math.log2(idx + 2)
    ideal_hits = min(len(expected), len(top))
    if ideal_hits == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(idx + 2) for idx in range(ideal_hits))
    if idcg == 0:
        return 0.0
    return round(dcg / idcg, 4)


def compute_metrics(expected_object_ids: list[str], predicted_object_ids: list[str], k: int) -> dict[str, float]:
    return {
        "recall_at_k": recall_at_k(expected_object_ids, predicted_object_ids, k),
        "precision_at_k": precision_at_k(expected_object_ids, predicted_object_ids, k),
        "mrr": mrr(expected_object_ids, predicted_object_ids, k),
        "ndcg": ndcg(expected_object_ids, predicted_object_ids, k),
    }
