from datetime import date

from src.services.knowledge.chunk_summary_service import apply_summary_update


def test_apply_summary_update_high_confidence_dates():
    chunk_fields, warnings = apply_summary_update(
        current_summary="旧摘要",
        current_certificate_number=None,
        current_certificate_date=None,
        current_expire_date=None,
        llm_result={
            "summary": "新摘要",
            "certificate_number": "NO-1,NO-2",
            "certificate_date": "2023-01-01,2024-01-01",
            "expire_date": "2026-01-01",
            "date_confidence": "high",
        },
    )
    assert chunk_fields["summary"] == "新摘要"
    assert chunk_fields["certificate_number"] == "NO-1,NO-2"
    assert chunk_fields["certificate_date"] == "2023-01-01,2024-01-01"
    assert chunk_fields["expire_date"].isoformat() == "2026-01-01"
    assert not warnings


def test_apply_summary_update_low_confidence_keeps_dates():
    chunk_fields, _ = apply_summary_update(
        current_summary="旧",
        current_certificate_number="KEEP-1",
        current_certificate_date="2020-01-01",
        current_expire_date=date(2020, 1, 1),
        llm_result={
            "summary": "新",
            "certificate_number": "NEW-1",
            "certificate_date": "2023-01-01",
            "date_confidence": "low",
        },
    )
    assert chunk_fields["certificate_number"] == "KEEP-1"
    assert chunk_fields["certificate_date"] == "2020-01-01"
    assert chunk_fields["expire_date"].isoformat() == "2020-01-01"
