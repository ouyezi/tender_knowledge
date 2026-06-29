from datetime import date

from src.services.knowledge.qualification_field_utils import (
    earliest_expire_date_from_qualification_info,
    format_qualification_record,
    normalize_qualification_info,
    parse_expire_date_value,
    parse_qualification_records,
)


def test_normalize_qualification_info_dedupes_records():
    raw = (
        "ISO9001|A001|2024-01-01|2026-12-31;"
        " ISO9001|A001|2024-01-01|2026-12-31 ;"
        "软件著作权|2020SR123|2020-06-01|2030-06-01"
    )
    assert normalize_qualification_info(raw) == (
        "ISO9001|A001|2024-01-01|2026-12-31;"
        "软件著作权|2020SR123|2020-06-01|2030-06-01"
    )


def test_parse_qualification_records_splits_pipe_fields():
    records = parse_qualification_records(
        "ISO9001|A001|2024-01-01|2026-12-31;营业执照||2024-02-01|长期有效"
    )
    assert len(records) == 2
    assert records[0].name == "ISO9001"
    assert records[0].number == "A001"
    assert records[0].issue_date == "2024-01-01"
    assert records[0].expire_text == "2026-12-31"
    assert records[1].expire_text == "长期有效"


def test_earliest_expire_date_from_qualification_info_picks_min():
    text = "ISO9001|A001|2024-01-01|2026-12-31;软著|SR1|2020-06-01|2024-06-01"
    assert earliest_expire_date_from_qualification_info(text) == date(2024, 6, 1)


def test_earliest_expire_date_ignores_non_iso_expire_text():
    assert earliest_expire_date_from_qualification_info("营业执照||2024-01-01|长期有效") is None


def test_format_qualification_record():
    assert format_qualification_record(
        name="ISO9001", number="A001", issue_date="2024-01-01", expire_text="2026-12-31"
    ) == "ISO9001|A001|2024-01-01|2026-12-31"


def test_parse_expire_date_value():
    assert parse_expire_date_value("2025-06-01") == date(2025, 6, 1)
    assert parse_expire_date_value(None) is None
