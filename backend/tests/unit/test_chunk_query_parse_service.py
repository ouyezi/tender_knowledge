from src.services.knowledge.chunk_query_parse_service import parse_search_query_response


MOCK_JSON = '{"semantic_query": "食品经营许可证 资质", "keyword": "食品经营许可证"}'


def test_parse_search_query_response_valid():
    result = parse_search_query_response(MOCK_JSON)
    assert result["semantic_query"] == "食品经营许可证 资质"
    assert result["keyword"] == "食品经营许可证"
