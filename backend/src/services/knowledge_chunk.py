from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from src.services.docx_outline_parser import OutlineNode

ChunkType = Literal["chapter", "material", "candidate"]
SuggestionSource = Literal["rule", "llm", "hybrid"]


@dataclass
class KnowledgeChunk:
    chunk_ref: str
    chunk_type: ChunkType
    title: str
    content_preview: str
    parent_chunk_ref: str | None = None


@dataclass
class ChunkClassificationResult:
    suggested_product_category_ids: list[UUID] = field(default_factory=list)
    suggested_chapter_taxonomy_id: UUID | None = None
    suggested_knowledge_type: str | None = None
    classification_confidence: float = 0.5
    suggestion_source: SuggestionSource = "rule"
    classification_rationale: str | None = None


def build_knowledge_chunks(
    *,
    outline_nodes: list[OutlineNode],
    materials: list[dict[str, Any]],
    candidates: list[dict[str, Any]] | None = None,
) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for node in outline_nodes:
        chunks.append(
            KnowledgeChunk(
                chunk_ref=node.temp_id,
                chunk_type="chapter",
                title=node.title,
                content_preview=node.title,
                parent_chunk_ref=node.parent_temp_id,
            )
        )
    for material in materials:
        content = str(material.get("content") or material.get("title") or "")
        chunks.append(
            KnowledgeChunk(
                chunk_ref=str(material["temp_id"]),
                chunk_type="material",
                title=str(material.get("title") or ""),
                content_preview=content[:8000],
                parent_chunk_ref=material.get("chapter_temp_id"),
            )
        )
    for candidate in candidates or []:
        chunks.append(
            KnowledgeChunk(
                chunk_ref=str(candidate["temp_id"]),
                chunk_type="candidate",
                title=str(candidate.get("title") or ""),
                content_preview=str(
                    candidate.get("content_preview") or candidate.get("content") or ""
                )[:8000],
                parent_chunk_ref=candidate.get("chapter_temp_id"),
            )
        )
    return chunks


def _apply_result_to_dict(item: dict[str, Any], result: ChunkClassificationResult) -> None:
    item["suggested_product_category_ids"] = [
        str(category_id) for category_id in result.suggested_product_category_ids
    ]
    item["suggested_chapter_taxonomy_id"] = (
        str(result.suggested_chapter_taxonomy_id)
        if result.suggested_chapter_taxonomy_id
        else None
    )
    item["suggested_knowledge_type"] = result.suggested_knowledge_type
    item["classification_confidence"] = result.classification_confidence
    item["suggestion_source"] = result.suggestion_source
    item["classification_rationale"] = result.classification_rationale
    if item.get("chapter_taxonomy_id") is None and result.suggested_chapter_taxonomy_id:
        item["chapter_taxonomy_id"] = str(result.suggested_chapter_taxonomy_id)
    if not item.get("product_category_ids"):
        item["product_category_ids"] = [
            str(category_id) for category_id in result.suggested_product_category_ids
        ]


def merge_classifications_into_suggestion(
    *,
    suggested_chapter_tree: list[dict[str, Any]],
    suggested_materials: list[dict[str, Any]],
    suggested_candidates: list[dict[str, Any]],
    chunks: list[KnowledgeChunk],
    results: dict[str, ChunkClassificationResult],
) -> dict[str, Any]:
    tree = [dict(item) for item in suggested_chapter_tree]
    materials = [dict(item) for item in suggested_materials]
    candidates = [dict(item) for item in suggested_candidates]
    for item in tree:
        result = results.get(str(item.get("temp_id")))
        if result:
            _apply_result_to_dict(item, result)
    for item in materials:
        result = results.get(str(item.get("temp_id")))
        if result:
            _apply_result_to_dict(item, result)
    for item in candidates:
        result = results.get(str(item.get("temp_id")))
        if result:
            _apply_result_to_dict(item, result)
    sources = {result.suggestion_source for result in results.values()}
    if not sources:
        task_source: SuggestionSource = "rule"
    elif len(sources) > 1:
        task_source = "hybrid"
    else:
        task_source = next(iter(sources))
    return {
        "suggested_chapter_tree": tree,
        "suggested_materials": materials,
        "suggested_candidates": candidates,
        "suggestion_source": task_source,
    }


def summarize_task_suggestion_source(results: dict[str, ChunkClassificationResult]) -> str:
    sources = {result.suggestion_source for result in results.values()}
    if not sources:
        return "rule"
    if len(sources) > 1:
        return "hybrid"
    return next(iter(sources))
