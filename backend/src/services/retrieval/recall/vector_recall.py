from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus
from src.services.retrieval.indexing.embedding_client import EmbeddingClient


@dataclass(slots=True)
class VectorRecallHit:
    entry: RetrievalIndexEntry
    score: float
    reason: str


@dataclass(slots=True)
class VectorRecallResult:
    hits: list[VectorRecallHit]
    vector_disabled_reason: str | None = None


class VectorRecallService:
    def __init__(self, db: Session, embedding_client: EmbeddingClient | None = None) -> None:
        self.db = db
        self.embedding_client = embedding_client or EmbeddingClient()

    def recall(self, *, kb_id: UUID, query: str, top_k: int) -> VectorRecallResult:
        query_text = (query or "").strip()
        if not query_text:
            return VectorRecallResult(hits=[])
        if not self.embedding_client.is_configured:
            return VectorRecallResult(hits=[], vector_disabled_reason="embedding_not_configured")
        embedded = self.embedding_client.embed_text(query_text)
        if not embedded.vector:
            return VectorRecallResult(
                hits=[],
                vector_disabled_reason=embedded.disabled_reason or "embedding_request_failed",
            )
        rows = (
            self.db.query(RetrievalIndexEntry)
            .filter(
                RetrievalIndexEntry.kb_id == kb_id,
                RetrievalIndexEntry.status == RetrievalIndexStatus.published,
            )
            .all()
        )
        hits: list[VectorRecallHit] = []
        for row in rows:
            if not row.embedding:
                continue
            score = self._cosine_similarity(embedded.vector, row.embedding)
            hits.append(
                VectorRecallHit(
                    entry=row,
                    score=round(score, 4),
                    reason="向量语义匹配",
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return VectorRecallResult(hits=hits[:top_k])

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        if not vec_a or not vec_b:
            return 0.0
        size = min(len(vec_a), len(vec_b))
        if size <= 0:
            return 0.0
        dot = sum(float(vec_a[i]) * float(vec_b[i]) for i in range(size))
        norm_a = math.sqrt(sum(float(vec_a[i]) ** 2 for i in range(size)))
        norm_b = math.sqrt(sum(float(vec_b[i]) ** 2 for i in range(size)))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        score = dot / (norm_a * norm_b)
        return max(0.0, min(1.0, (score + 1) / 2))
