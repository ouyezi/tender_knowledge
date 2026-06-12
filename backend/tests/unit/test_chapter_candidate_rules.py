from src.services.chapter_candidate_rules import resolve_candidate_type


def test_technical_solution_maps_to_ku_solution():
    result = resolve_candidate_type(taxonomy_code="technical_solution")
    assert result.candidate_type == "ku"
    assert result.suggested_knowledge_type == "solution"
