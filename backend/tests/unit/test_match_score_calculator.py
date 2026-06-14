from src.services.retrieval.match_score_calculator import MatchScoreCalculator


def test_calculate_match_score_with_default_weights():
    calculator = MatchScoreCalculator()

    result = calculator.calculate(
        product_category_score=1.0,
        chapter_taxonomy_score=0.5,
        title_similarity_score=0.8,
        level_order_score=0.9,
        knowledge_coverage_score=0.4,
    )

    assert round(result["match_score"], 4) == 0.74
    assert round(result["coverage_rate"], 4) == 0.72
    assert result["score_detail"]["product_category"] == 0.3
    assert result["score_detail"]["chapter_taxonomy"] == 0.15


def test_calculate_match_score_with_custom_weights():
    calculator = MatchScoreCalculator(
        {
            "product_category": 0.2,
            "chapter_taxonomy": 0.2,
            "title_similarity": 0.2,
            "level_order": 0.2,
            "knowledge_coverage": 0.2,
        }
    )

    result = calculator.calculate(
        product_category_score=1.0,
        chapter_taxonomy_score=1.0,
        title_similarity_score=0.0,
        level_order_score=0.0,
        knowledge_coverage_score=0.5,
    )

    assert round(result["match_score"], 4) == 0.5
    assert round(result["coverage_rate"], 4) == 0.5
