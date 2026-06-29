from datetime import date

from src.services.knowledge.chunk_summary_service import apply_summary_update


def test_apply_summary_update_high_confidence_qualification_info():
    chunk_fields, warnings = apply_summary_update(
        current_summary="旧摘要",
        current_qualification_info=None,
        current_expire_date=None,
        llm_result={
            "summary": "新摘要",
            "qualification_info": "ISO9001|NO-1|2023-01-01|2026-01-01",
            "date_confidence": "high",
        },
    )
    assert chunk_fields["summary"] == "新摘要"
    assert chunk_fields["qualification_info"] == "ISO9001|NO-1|2023-01-01|2026-01-01"
    assert chunk_fields["expire_date"].isoformat() == "2026-01-01"
    assert not warnings


def test_apply_summary_update_low_confidence_keeps_qualification_info():
    chunk_fields, _ = apply_summary_update(
        current_summary="旧",
        current_qualification_info="KEEP|K1|2020-01-01|2025-01-01",
        current_expire_date=date(2025, 1, 1),
        llm_result={
            "summary": "新",
            "qualification_info": "NEW|N1|2023-01-01|2028-01-01",
            "date_confidence": "low",
        },
    )
    assert chunk_fields["summary"] == "新"
    assert chunk_fields["qualification_info"] == "KEEP|K1|2020-01-01|2025-01-01"
    assert chunk_fields["expire_date"].isoformat() == "2025-01-01"
