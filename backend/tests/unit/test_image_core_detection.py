from src.services.knowledge.image_vision_service import is_core_image_extraction


def test_core_image_by_role():
    assert is_core_image_extraction(
        {"extracted_facts": {"information_role": "core"}, "caption": "图", "ocr_text": ""}
    )
    assert not is_core_image_extraction(
        {
            "extracted_facts": {"information_role": "auxiliary"},
            "caption": "ISO9001 证书",
            "ocr_text": "认证证书",
        }
    )


def test_core_image_inferred_from_cert_keywords():
    assert is_core_image_extraction({"caption": "ISO9001 认证证书", "ocr_text": "", "extracted_facts": {}})
