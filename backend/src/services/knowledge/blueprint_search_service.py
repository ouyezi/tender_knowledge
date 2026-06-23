from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.models.blueprint_embedding import BlueprintEmbedding
from src.models.knowledge_blueprint import BlueprintStatus, KnowledgeBlueprint
from src.services.knowledge.blueprint_index_text import (
    build_highlights,
    exact_match_bonus,
    keyword_score,
)
from src.services.knowledge.blueprint_service import _apply_tag_filter


class BlueprintSearchValidationError(Exception):
    pass


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    max_score = max(scores)
    if max_score <= 0:
        return [0.0 for _ in scores]
    return [score / max_score for score in scores]


def _effective_vector_scores(raw_scores: list[float], *, min_similarity: float) -> list[float]:
    if not raw_scores:
        return []
    max_raw = max(raw_scores)
    if max_raw < min_similarity:
        return [0.0 for _ in raw_scores]
    normalized = _normalize_scores(raw_scores)
    blended: list[float] = []
    for raw, norm in zip(raw_scores, normalized):
        if raw < min_similarity:
            blended.append(0.0)
        else:
            blended.append(0.5 * norm + 0.5 * raw)
    return blended


def search_blueprints(
    db: Session,
    *,
    kb_id: UUID,
    semantic_query: str,
    keyword: str,
    product_tags: list[str],
    industry_tags: list[str],
    scenario_tags: list[str],
    vector_weight: float,
    keyword_weight: float,
    top_k: int,
    query_vector: list[float] | None,
) -> dict[str, Any]:
    semantic = semantic_query.strip()
    kw = keyword.strip()
    if not semantic and not kw:
        raise BlueprintSearchValidationError("semantic_query and keyword cannot both be empty")

    query = (
        db.query(KnowledgeBlueprint, BlueprintEmbedding)
        .outerjoin(
            BlueprintEmbedding,
            BlueprintEmbedding.blueprint_id == KnowledgeBlueprint.blueprint_id,
        )
        .filter(
            KnowledgeBlueprint.kb_id == kb_id,
            KnowledgeBlueprint.status == BlueprintStatus.active,
        )
    )
    query = _apply_tag_filter(query, KnowledgeBlueprint.product_tags, product_tags)
    query = _apply_tag_filter(query, KnowledgeBlueprint.industry_tags, industry_tags)
    query = _apply_tag_filter(query, KnowledgeBlueprint.scenario_tags, scenario_tags)

    rows = query.all()
    candidates_scanned = len(rows)

    raw_keyword_scores: list[float] = []
    raw_vector_scores: list[float] = []
    prepared: list[tuple[KnowledgeBlueprint, BlueprintEmbedding | None, float, float]] = []

    for blueprint, embedding_row in rows:
        search_text = embedding_row.search_text if embedding_row else ""
        k_score = (
            keyword_score(
                keyword=kw,
                name=blueprint.name,
                description=blueprint.description,
                search_text=search_text,
                name_weight=settings.blueprint_search_name_keyword_weight,
                body_weight=settings.blueprint_search_body_keyword_weight,
            )
            if kw
            else 0.0
        )
        v_score = 0.0
        if query_vector and embedding_row and embedding_row.embedding is not None:
            vec = embedding_row.embedding
            if not isinstance(vec, list):
                try:
                    vec = list(vec)
                except TypeError:
                    vec = None
            if isinstance(vec, list):
                v_score = max(0.0, float(_cosine_similarity(vec, query_vector)))
        raw_keyword_scores.append(k_score)
        raw_vector_scores.append(v_score)
        prepared.append((blueprint, embedding_row, k_score, v_score))

    norm_k = _normalize_scores(raw_keyword_scores)
    eff_v = _effective_vector_scores(
        raw_vector_scores,
        min_similarity=settings.blueprint_search_vector_min_similarity,
    )

    items: list[dict[str, Any]] = []
    for idx, (blueprint, embedding_row, k_score, v_score) in enumerate(prepared):
        match_bonus = exact_match_bonus(
            semantic_query=semantic,
            keyword=kw,
            name=blueprint.name,
            boost=settings.blueprint_search_exact_match_boost,
        )
        final = (
            vector_weight * eff_v[idx]
            + keyword_weight * norm_k[idx]
            + match_bonus
        )
        if final <= 0:
            continue
        highlights = (
            build_highlights(
                keyword=kw,
                name=blueprint.name,
                description=blueprint.description,
                search_text=embedding_row.search_text if embedding_row else "",
            )
            if kw
            else []
        )
        items.append(
            {
                "blueprint_id": str(blueprint.blueprint_id),
                "name": blueprint.name,
                "description": blueprint.description,
                "product_tags": blueprint.product_tags or [],
                "industry_tags": blueprint.industry_tags or [],
                "scenario_tags": blueprint.scenario_tags or [],
                "source_chapter_title": blueprint.source_chapter_title,
                "version": blueprint.version,
                "updated_at": blueprint.updated_at.isoformat() if blueprint.updated_at else None,
                "embedding_status": embedding_row.embedding_status if embedding_row else "pending",
                "score": round(final, 4),
                "score_detail": {
                    "vector_score": round(v_score, 4),
                    "keyword_score": round(k_score, 4),
                    "exact_match_bonus": round(match_bonus, 4),
                    "vector_weight": vector_weight,
                    "keyword_weight": keyword_weight,
                },
                "highlights": highlights,
            }
        )

    items.sort(key=lambda item: item["score"], reverse=True)
    top_k = max(1, min(int(top_k or 10), 50))
    items = items[:top_k]

    vector_enabled = query_vector is not None
    return {
        "items": items,
        "total": len(items),
        "search_meta": {
            "vector_enabled": vector_enabled,
            "keyword_enabled": bool(kw),
            "candidates_scanned": candidates_scanned,
        },
    }
