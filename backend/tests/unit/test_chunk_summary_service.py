from datetime import date

from src.services.knowledge.chunk_summary_service import apply_summary_update


def test_apply_summary_update_high_confidence_dates():
    chunk_fields, warnings = apply_summary_update(
        current_summary="旧摘要",
        current_issue_date=None,
        current_expire_date=None,
        llm_result={
            "summary": "新摘要",
            "issue_date": "2023-01-01",
            "expire_date": "2026-01-01",
            "date_confidence": "high",
        },
    )
    assert chunk_fields["summary"] == "新摘要"
    assert chunk_fields["issue_date"].isoformat() == "2023-01-01"
    assert not warnings


def test_apply_summary_update_low_confidence_keeps_dates():
    chunk_fields, _ = apply_summary_update(
        current_summary="旧",
        current_issue_date=date(2020, 1, 1),
        current_expire_date=None,
        llm_result={"summary": "新", "issue_date": "2023-01-01", "date_confidence": "low"},
    )
    assert chunk_fields["issue_date"].isoformat() == "2020-01-01"
