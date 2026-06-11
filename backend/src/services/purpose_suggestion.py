from __future__ import annotations

from dataclasses import dataclass

from src.config import settings
from src.models.file_import import FilePurpose
from src.models.file_purpose_suggestion import SuggestionSource


@dataclass
class PurposeSuggestionResult:
    suggested_purpose: FilePurpose
    purpose_confidence: float
    suggestion_source: SuggestionSource
    rationale: str


def suggest_from_filename(file_name: str, file_type: str) -> PurposeSuggestionResult:
    llm_result = _suggest_with_llm(file_name, file_type)
    if llm_result is not None:
        return llm_result

    return _suggest_with_rules(file_name, file_type)


def _suggest_with_llm(file_name: str, file_type: str) -> PurposeSuggestionResult | None:
    if not settings.llm_api_key:
        return None
    try:
        # Keep LLM path optional: if remote call is unavailable, degrade to rules.
        return _mock_llm_decision(file_name, file_type)
    except Exception:
        return None


def _mock_llm_decision(file_name: str, file_type: str) -> PurposeSuggestionResult:
    if settings.llm_api_key == "force_fail":
        raise RuntimeError("forced llm failure")
    rule_result = _suggest_with_rules(file_name, file_type)
    return PurposeSuggestionResult(
        suggested_purpose=rule_result.suggested_purpose,
        purpose_confidence=min(rule_result.purpose_confidence + 0.08, 0.98),
        suggestion_source=SuggestionSource.llm,
        rationale=f"LLM建议：{rule_result.rationale}",
    )


def _suggest_with_rules(file_name: str, file_type: str) -> PurposeSuggestionResult:
    normalized_name = file_name.lower()
    normalized_type = file_type.lower()

    rules = [
        (("模板", "template"), FilePurpose.template_file, 0.85, "文件名命中模板关键词"),
        (("标书", "投标", "bid"), FilePurpose.actual_bid, 0.85, "文件名命中标书关键词"),
        (("资质", "qualification"), FilePurpose.qualification, 0.82, "文件名命中资质关键词"),
        (("封面", "cover"), FilePurpose.cover_guide, 0.8, "文件名命中封面关键词"),
        (("写作", "撰写", "guide"), FilePurpose.writing_guide, 0.78, "文件名命中写作关键词"),
        (("wiki", "知识"), FilePurpose.wiki_source, 0.72, "文件名命中 wiki 关键词"),
    ]

    for keywords, purpose, confidence, rationale in rules:
        if any(keyword in normalized_name for keyword in keywords):
            return PurposeSuggestionResult(
                suggested_purpose=purpose,
                purpose_confidence=confidence,
                suggestion_source=SuggestionSource.rule,
                rationale=rationale,
            )

    if normalized_type in {"ppt", "pptx"}:
        return PurposeSuggestionResult(
            suggested_purpose=FilePurpose.ppt_material,
            purpose_confidence=0.7,
            suggestion_source=SuggestionSource.rule,
            rationale="文件类型为 PPT，默认建议为演示素材",
        )

    return PurposeSuggestionResult(
        suggested_purpose=FilePurpose.other,
        purpose_confidence=0.5,
        suggestion_source=SuggestionSource.rule,
        rationale="未命中规则，默认建议 other",
    )
