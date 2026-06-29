from __future__ import annotations

import pytest

from src.services.knowledge.taxonomy_service import (
    TaxonomyValidationError,
    expand_business_line_labels,
    get_taxonomy_label,
    list_taxonomy,
    validate_application_type_code,
    validate_block_type_code,
    validate_business_line_codes,
    validate_dynamic_type_code,
)


def test_list_taxonomy_filters_by_dimension(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    rows = list_taxonomy(db_session, dimension="block_type")
    assert rows
    assert {item.dimension for item in rows} == {"block_type"}


def test_validate_block_type_code_accepts_seed(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    assert validate_block_type_code(db_session, "product_solution") == "product_solution"


def test_validate_block_type_code_rejects_unknown(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    with pytest.raises(TaxonomyValidationError):
        validate_block_type_code(db_session, "not_real")


def test_validate_application_type_code_accepts_seed(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    assert (
        validate_application_type_code(db_session, "preferred_reference")
        == "preferred_reference"
    )


def test_validate_dynamic_type_code_accepts_seed(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    assert validate_dynamic_type_code(db_session, "brand_authorization") == "brand_authorization"


def test_validate_business_line_codes_normalizes_empty(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    assert validate_business_line_codes(db_session, []) == ["general"]


def test_validate_business_line_codes_rejects_unknown(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    with pytest.raises(TaxonomyValidationError):
        validate_business_line_codes(db_session, ["meal_subsidy", "unknown"])


def test_get_taxonomy_label_returns_label(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    assert get_taxonomy_label(db_session, "business_line", "insurance") == "保险"


def test_expand_business_line_labels_fallback_to_code(db_session, seeded_taxonomy):
    _ = seeded_taxonomy
    labels = expand_business_line_labels(db_session, ["insurance", "unknown_code"])
    assert labels == ["保险", "unknown_code"]
