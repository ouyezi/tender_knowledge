from datetime import date

from src.services.knowledge.certificate_field_utils import (
    earliest_expire_date,
    earliest_expire_date_from_csv,
    normalize_certificate_date,
    normalize_certificate_number,
    parse_expire_date_value,
)


def test_normalize_certificate_number_dedupes_and_trims():
    assert normalize_certificate_number(" A001 , B002 , A001 ") == "A001,B002"


def test_normalize_certificate_date():
    assert normalize_certificate_date("2024-01-01, 2025-06-01") == "2024-01-01,2025-06-01"
    assert normalize_certificate_date(None) is None


def test_earliest_expire_date_picks_min():
    assert earliest_expire_date(["2025-12-31", "2024-06-01", "invalid"]) == date(2024, 6, 1)
    assert earliest_expire_date([]) is None


def test_earliest_expire_date_from_csv():
    assert earliest_expire_date_from_csv("2025-12-31,2024-06-01") == date(2024, 6, 1)


def test_parse_expire_date_value():
    assert parse_expire_date_value("2025-06-01") == date(2025, 6, 1)
    assert parse_expire_date_value("2025-12-31,2024-06-01") == date(2024, 6, 1)
