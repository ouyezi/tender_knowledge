from __future__ import annotations

from src.services.knowledge.prefill_service import prefill_knowledge_attributes


def test_prefill_parses_json(monkeypatch):
    monkeypatch.setattr(
        "src.services.knowledge.prefill_service._chat_with_timeout",
        lambda **kw: '{"title":"T","summary":"S","knowledge_type":"fact","category":"technical","status":"draft"}',
    )
    result = prefill_knowledge_attributes(content="正文", metadata={})
    assert result["title"] == "T"
    assert result["summary"] == "S"
    assert result["knowledge_type"] == "fact"
    assert result["category"] == "technical"
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
        metadata={"source_type": "bid", "file_name": "demo.docx"},
    )
    assert result["warnings"] == ["prefill_timeout"]
    assert result["source_type"] == "bid"
    assert result["file_name"] == "demo.docx"
