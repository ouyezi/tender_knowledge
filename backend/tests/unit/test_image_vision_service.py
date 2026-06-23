from src.services.knowledge.image_vision_service import parse_vision_response


def test_parse_vision_response_valid():
    raw = (
        '{"caption":"证书扫描件","ocr_text":"ISO9001",'
        '"extracted_facts":{"confidence":"high","expire_date":"2026-01-01"}}'
    )
    result = parse_vision_response(raw)
    assert result["caption"] == "证书扫描件"
    assert result["extracted_facts"]["confidence"] == "high"
