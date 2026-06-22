from src.services.knowledge.blueprint_query_parse_service import parse_search_query_response

MOCK_JSON = """
{
  "semantic_query": "政务云 技术架构 章节",
  "keyword": "政务云 技术架构",
  "product_tags": ["政务云"],
  "industry_tags": ["政府"],
  "scenario_tags": []
}
"""


def test_parse_search_query_response_valid():
    result = parse_search_query_response(MOCK_JSON)
    assert result["semantic_query"] == "政务云 技术架构 章节"
    assert result["keyword"] == "政务云 技术架构"
    assert result["product_tags"] == ["政务云"]
