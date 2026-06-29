from __future__ import annotations

from src.services.knowledge.prefill_service import prefill_knowledge_attributes


def test_prefill_parses_json(monkeypatch):
    monkeypatch.setattr(
        "src.services.knowledge.prefill_service._chat_with_timeout",
        lambda **kw: '{"title":"T","summary":"S","knowledge_type":"fact","block_type_code":"product_solution","status":"draft"}',
    )
    result = prefill_knowledge_attributes(content="正文", metadata={})
    assert result["title"] == "T"
    assert result["summary"] == "S"
    assert result["knowledge_type"] == "fact"
    assert result["block_type_code"] == "product_solution"
    assert result["status"] == "draft"
    assert result.get("warnings") is None


def test_prefill_timeout_returns_warning(monkeypatch):
    def slow(**kw):
        raise TimeoutError("timed out")

    monkeypatch.setattr(
        "src.services.knowledge.prefill_service._chat_with_timeout",
        slow,
    )
    result = prefill_knowledge_attributes(
        content="正文",
        metadata={"file_name": "demo.docx"},
    )
    assert result["warnings"] == ["prefill_timeout"]
    assert result["file_name"] == "demo.docx"


def test_normalize_prefill_maps_taxonomy_codes(monkeypatch):
    monkeypatch.setattr(
        "src.services.knowledge.prefill_service._chat_with_timeout",
        lambda **kw: (
            '{"title":"T","block_type_code":"ip_patent",'
            '"application_type_code":"fact_extraction","business_line_codes":["meal_subsidy"]}'
        ),
    )
    result = prefill_knowledge_attributes(content="x", metadata={})
    assert result["block_type_code"] == "ip_patent"
    assert result["application_type_code"] == "fact_extraction"
    assert result["business_line_codes"] == ["meal_subsidy"]


def test_normalize_prefill_uses_content_type_hint(monkeypatch):
    monkeypatch.setattr(
        "src.services.knowledge.prefill_service._chat_with_timeout",
        lambda **kw: '{"title":"T","content_type":"text","knowledge_type":"fact"}',
    )
    result = prefill_knowledge_attributes(
        content="x",
        metadata={"content_type_hint": "mixed", "asset_summary": {"has_table": True}},
    )
    assert result["content_type"] == "mixed"


def test_prefill_maps_certificate_fields(monkeypatch):
    monkeypatch.setattr(
        "src.services.knowledge.prefill_service._chat_with_timeout",
        lambda **kw: (
            '{"title":"T","certificate_number":"A1,B2","certificate_date":"2024-01-01,2025-01-01",'
            '"expire_date":"2025-06-01,2024-12-31"}'
        ),
    )
    result = prefill_knowledge_attributes(content="证书", metadata={})
    assert result["certificate_number"] == "A1,B2"
    assert result["certificate_date"] == "2024-01-01,2025-01-01"
    assert result["expire_date"] == "2024-12-31"
    assert "issue_date" not in result
    assert "winning_flag" not in result


def test_build_user_prompt_includes_catalog():
    from src.services.knowledge.knowledge_prefill_context import build_user_prompt

    prompt = build_user_prompt(
        content="正文",
        context={
            "catalog_breadcrumb": "第一章 > 资质",
            "chapter_title": "资质",
            "file_name": "demo.docx",
        },
    )
    assert "第一章 > 资质" in prompt
    assert "demo.docx" in prompt
