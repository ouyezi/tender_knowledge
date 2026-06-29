from datetime import date

from src.services.knowledge.taxonomy_field_utils import (
    compute_is_expired,
    normalize_business_line_codes,
)


def test_normalize_business_line_codes_empty_defaults_general():
    assert normalize_business_line_codes([]) == ["general"]
    assert normalize_business_line_codes(None) == ["general"]


def test_normalize_business_line_codes_dedupes():
    assert normalize_business_line_codes(["meal_subsidy", "meal_subsidy"]) == [
        "meal_subsidy"
    ]


def test_compute_is_expired():
    assert compute_is_expired(None) is False
    assert compute_is_expired(date(2099, 1, 1)) is False
    assert compute_is_expired(date(2000, 1, 1)) is True
