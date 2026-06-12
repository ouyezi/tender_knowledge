from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy.orm import Session

from src.services.classification_rule_index import (
    ClassificationRuleIndex,
    load_classification_index,
    match_chapter_taxonomy,
    match_product_category,
)
from src.services.knowledge_chunk import ChunkClassificationResult, KnowledgeChunk
from src.services.llm_client import chat_completion, is_llm_available, truncate_for_llm

_KNOWLEDGE_TYPE_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("资质", "证照", "荣誉"), "qualification"),
    (("产品", "功能", "平台"), "product"),
    (("方案", "服务", "实施"), "scheme"),
]

_LLM_SYSTEM_PROMPT = (
    "你是标书知识块分类助手。根据单块标题与摘要，输出 JSON："
    '{"chapter_taxonomy_hint":"","product_category_hint":"","knowledge_type":"scheme|product|qualification|other","confidence":0.0}'
    "。只返回 JSON，不要解释。"
)


def _rule_classify(
    chunk: KnowledgeChunk,
    *,
    index: ClassificationRuleIndex,
) -> ChunkClassificationResult:
    text = f"{chunk.title}\n{chunk.content_preview}"
    product_ids: list[UUID] = []
    taxonomy_id: UUID | None = None
    knowledge_type: str | None = None
    confidence = 0.5
    rationales: list[str] = []

    product_hit = match_product_category(text, index=index)
    if product_hit:
        product_ids = [product_hit.category_id]
        confidence = max(confidence, product_hit.confidence)
        rationales.append(product_hit.rationale)

    if chunk.chunk_type in {"chapter", "candidate"}:
        taxonomy_hit = match_chapter_taxonomy(text, index=index)
        if taxonomy_hit:
            taxonomy_id = taxonomy_hit.taxonomy_id
            confidence = max(confidence, taxonomy_hit.confidence)
            rationales.append(taxonomy_hit.rationale)

    if chunk.chunk_type == "candidate":
        lowered = text.lower()
        for keywords, ktype in _KNOWLEDGE_TYPE_KEYWORDS:
            if any(keyword in lowered for keyword in keywords):
                knowledge_type = ktype
                confidence = max(confidence, 0.72)
                rationales.append(f"知识类型关键词命中：{ktype}")
                break

    return ChunkClassificationResult(
        suggested_product_category_ids=product_ids,
        suggested_chapter_taxonomy_id=taxonomy_id,
        suggested_knowledge_type=knowledge_type,
        classification_confidence=confidence,
        suggestion_source="rule",
        classification_rationale="；".join(rationales) if rationales else "未命中规则",
    )


def _parse_llm_json(content: str) -> dict | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _llm_classify(
    chunk: KnowledgeChunk,
    *,
    index: ClassificationRuleIndex,
) -> ChunkClassificationResult | None:
    user_prompt = truncate_for_llm(f"标题：{chunk.title}\n内容：{chunk.content_preview}")
    response = chat_completion(system_prompt=_LLM_SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=256)
    if response is None:
        return None
    payload = _parse_llm_json(response.content)
    if payload is None:
        return None

    product_ids: list[UUID] = []
    product_hint = str(payload.get("product_category_hint") or "").strip()
    if product_hint:
        hit = match_product_category(product_hint, index=index)
        if hit:
            product_ids = [hit.category_id]

    taxonomy_id: UUID | None = None
    taxonomy_hint = str(payload.get("chapter_taxonomy_hint") or chunk.title).strip()
    taxonomy_hit = match_chapter_taxonomy(taxonomy_hint, index=index)
    if taxonomy_hit:
        taxonomy_id = taxonomy_hit.taxonomy_id

    knowledge_type = payload.get("knowledge_type")
    if isinstance(knowledge_type, str):
        knowledge_type = knowledge_type.strip() or None
    else:
        knowledge_type = None

    try:
        confidence = float(payload.get("confidence", 0.75))
    except (TypeError, ValueError):
        confidence = 0.75

    return ChunkClassificationResult(
        suggested_product_category_ids=product_ids,
        suggested_chapter_taxonomy_id=taxonomy_id,
        suggested_knowledge_type=knowledge_type if chunk.chunk_type == "candidate" else None,
        classification_confidence=min(max(confidence, 0.0), 1.0),
        suggestion_source="llm",
        classification_rationale="LLM 块级分类建议",
    )


def _merge_results(
    rule_result: ChunkClassificationResult,
    llm_result: ChunkClassificationResult | None,
) -> ChunkClassificationResult:
    if llm_result is None:
        return rule_result
    if llm_result.classification_confidence >= rule_result.classification_confidence:
        merged = ChunkClassificationResult(
            suggested_product_category_ids=llm_result.suggested_product_category_ids
            or rule_result.suggested_product_category_ids,
            suggested_chapter_taxonomy_id=llm_result.suggested_chapter_taxonomy_id
            or rule_result.suggested_chapter_taxonomy_id,
            suggested_knowledge_type=llm_result.suggested_knowledge_type
            or rule_result.suggested_knowledge_type,
            classification_confidence=max(
                llm_result.classification_confidence,
                rule_result.classification_confidence,
            ),
            suggestion_source="hybrid"
            if rule_result.classification_confidence > 0.5
            and (
                llm_result.suggested_chapter_taxonomy_id
                or llm_result.suggested_product_category_ids
            )
            else "llm",
            classification_rationale=llm_result.classification_rationale,
        )
        return merged
    rule_result.suggestion_source = "hybrid"
    return rule_result


def classify_chunk(
    db: Session,
    *,
    kb_id: UUID,
    chunk: KnowledgeChunk,
    index: ClassificationRuleIndex | None = None,
) -> tuple[ChunkClassificationResult, bool]:
    """Classify one knowledge chunk. Returns (result, degraded_to_rule)."""
    rule_index = index or load_classification_index(db, kb_id=kb_id)
    rule_result = _rule_classify(chunk, index=rule_index)
    if not is_llm_available():
        return rule_result, True
    llm_result = _llm_classify(chunk, index=rule_index)
    if llm_result is None:
        return rule_result, True
    return _merge_results(rule_result, llm_result), False
