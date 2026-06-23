from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.knowledge.chunk_index_text import (
    build_chunk_highlights,
    chunk_exact_match_bonus,
    chunk_keyword_score,
)


class ChunkSearchValidationError(Exception):
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


def _as_vector(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    try:
        return list(value)
    except TypeError:
        return None


def search_knowledge_chunks(
    db: Session,
    *,
    kb_id: UUID,
    semantic_query: str,
    keyword: str,
    vector_weight: float,
    keyword_weight: float,
    title_vector_weight: float,
    summary_vector_weight: float,
    content_vector_weight: float,
    top_k: int,
    query_vector: list[float] | None,
) -> dict[str, Any]:
    semantic = semantic_query.strip()
    kw = keyword.strip()
    if not semantic and not kw:
        raise ChunkSearchValidationError("semantic_query and keyword cannot both be empty")

    rows = (
        db.query(KnowledgeChunk, ChunkEmbedding)
        .outerjoin(
            ChunkEmbedding,
            (ChunkEmbedding.object_type == "chunk")
            & (ChunkEmbedding.object_id == KnowledgeChunk.id),
        )
        .filter(
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.is_latest.is_(True),
            KnowledgeChunk.embedding_status == "ready",
        )
        .all()
    )
    candidates_scanned = len(rows)

    raw_keyword_scores: list[float] = []
    raw_vector_scores: list[float] = []
    prepared: list[tuple[KnowledgeChunk, ChunkEmbedding | None, float, float, float, float, float]] = []

    weight_sum = max(title_vector_weight + summary_vector_weight + content_vector_weight, 1e-9)

    for chunk, embedding_row in rows:
        k_score = (
            chunk_keyword_score(
                keyword=kw,
                title=chunk.title,
                summary=chunk.summary,
                content=chunk.content,
                title_weight=settings.chunk_search_title_keyword_weight,
                body_weight=settings.chunk_search_body_keyword_weight,
            )
            if kw
            else 0.0
        )
        title_v = summary_v = content_v = 0.0
        if query_vector and embedding_row is not None:
            title_vec = _as_vector(embedding_row.title_embedding)
            summary_vec = _as_vector(embedding_row.summary_embedding)
            content_vec = _as_vector(embedding_row.content_embedding)
            if title_vec:
                title_v = max(0.0, float(_cosine_similarity(title_vec, query_vector)))
            if summary_vec:
                summary_v = max(0.0, float(_cosine_similarity(summary_vec, query_vector)))
            if content_vec:
                content_v = max(0.0, float(_cosine_similarity(content_vec, query_vector)))
        v_score = (
            title_vector_weight * title_v
            + summary_vector_weight * summary_v
            + content_vector_weight * content_v
        ) / weight_sum

        raw_keyword_scores.append(k_score)
        raw_vector_scores.append(v_score)
        prepared.append((chunk, embedding_row, k_score, v_score, title_v, summary_v, content_v))

    norm_k = _normalize_scores(raw_keyword_scores)
    eff_v = _effective_vector_scores(
        raw_vector_scores,
        min_similarity=settings.chunk_search_vector_min_similarity,
    )

    items: list[dict[str, Any]] = []
    for idx, (chunk, _embedding_row, k_score, v_score, title_v, summary_v, content_v) in enumerate(
        prepared
    ):
        match_bonus = chunk_exact_match_bonus(
            semantic_query=semantic,
            keyword=kw,
            title=chunk.title,
            boost=settings.chunk_search_exact_match_boost,
        )
        final = vector_weight * eff_v[idx] + keyword_weight * norm_k[idx] + match_bonus
        if final <= 0:
            continue
        highlights = (
            build_chunk_highlights(
                keyword=kw,
                title=chunk.title,
                summary=chunk.summary,
                content=chunk.content,
            )
            if kw
            else []
        )
        items.append(
            {
                "id": chunk.id,
                "title": chunk.title,
                "summary": chunk.summary,
                "version": chunk.version,
                "category": chunk.category,
                "knowledge_type": chunk.knowledge_type,
                "status": chunk.status,
                "embedding_status": chunk.embedding_status,
                "token_count": chunk.token_count,
                "update_time": chunk.update_time.isoformat() if chunk.update_time else None,
                "score": round(final, 4),
                "score_detail": {
                    "vector_score": round(v_score, 4),
                    "keyword_score": round(k_score, 4),
                    "title_vector": round(title_v, 4),
                    "summary_vector": round(summary_v, 4),
                    "content_vector": round(content_v, 4),
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

    return {
        "items": items,
        "total": len(items),
        "search_meta": {
            "vector_enabled": query_vector is not None,
            "keyword_enabled": bool(kw),
            "candidates_scanned": candidates_scanned,
        },
    }
