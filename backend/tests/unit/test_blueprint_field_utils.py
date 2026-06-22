from src.services.knowledge.blueprint_field_utils import (
    CONTENT_DESCRIPTION_MAX,
    SUGGESTED_STRUCTURE_MD_MAX,
    TENDER_RESPONSE_HINT_MAX,
    truncate_blueprint_field,
)


def test_truncate_blueprint_field_returns_none_for_blank():
    assert truncate_blueprint_field("   ", max_len=200) is None


def test_truncate_blueprint_field_truncates_long_text():
    text = "章" * 250
    result = truncate_blueprint_field(text, max_len=CONTENT_DESCRIPTION_MAX)
    assert result is not None
    assert len(result) == CONTENT_DESCRIPTION_MAX


def test_constants_match_design_spec():
    assert CONTENT_DESCRIPTION_MAX == 200
    assert TENDER_RESPONSE_HINT_MAX == 300
    assert SUGGESTED_STRUCTURE_MD_MAX == 1500
