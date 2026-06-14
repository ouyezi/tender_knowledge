from __future__ import annotations

from dataclasses import dataclass


DEFAULT_WEIGHTS = {
    "product_category": 0.3,
    "chapter_taxonomy": 0.3,
    "title_similarity": 0.2,
    "level_order": 0.1,
    "knowledge_coverage": 0.1,
}


@dataclass(slots=True)
class MatchScoreCalculator:
    weights: dict[str, float] | None = None

    def __post_init__(self) -> None:
        merged = dict(DEFAULT_WEIGHTS)
        if self.weights:
            merged.update(self.weights)
        self.weights = merged

    def calculate(
        self,
        *,
        product_category_score: float,
        chapter_taxonomy_score: float,
        title_similarity_score: float,
        level_order_score: float,
        knowledge_coverage_score: float,
    ) -> dict[str, float | dict[str, float]]:
        assert self.weights is not None
        score_detail = {
            "product_category": round(self.weights["product_category"] * self._clamp(product_category_score), 4),
            "chapter_taxonomy": round(self.weights["chapter_taxonomy"] * self._clamp(chapter_taxonomy_score), 4),
            "title_similarity": round(self.weights["title_similarity"] * self._clamp(title_similarity_score), 4),
            "level_order": round(self.weights["level_order"] * self._clamp(level_order_score), 4),
            "knowledge_coverage": round(
                self.weights["knowledge_coverage"] * self._clamp(knowledge_coverage_score), 4
            ),
        }
        match_score = round(sum(score_detail.values()), 4)
        score_count = len(score_detail)
        coverage_rate = round(sum(v / self.weights[k] for k, v in score_detail.items()) / score_count, 4)
        return {
            "match_score": match_score,
            "coverage_rate": coverage_rate,
            "score_detail": score_detail,
        }

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
