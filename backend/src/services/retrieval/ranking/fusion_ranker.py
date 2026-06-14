from __future__ import annotations

from dataclasses import dataclass

from src.models.retrieval_index_entry import RetrievalIndexEntry
from src.services.retrieval.recall.keyword_recall import KeywordRecallHit
from src.services.retrieval.recall.metadata_recall import MetadataRecallHit
from src.services.retrieval.recall.vector_recall import VectorRecallHit


@dataclass(slots=True)
class FusionRankedHit:
    entry: RetrievalIndexEntry
    score: float
    score_detail: dict[str, float]
    hit_reason: str


class FusionRanker:
    def rank(
        self,
        *,
        metadata_hits: list[MetadataRecallHit],
        keyword_hits: list[KeywordRecallHit],
        vector_hits: list[VectorRecallHit],
        top_k: int,
    ) -> list[FusionRankedHit]:
        merged: dict[str, dict] = {}
        for item in metadata_hits:
            bucket = merged.setdefault(self._key(item.entry), self._new_bucket(item.entry))
            bucket["metadata"] = max(bucket["metadata"], item.score)
            bucket["reason"]["metadata"] = item.reason
        for item in keyword_hits:
            bucket = merged.setdefault(self._key(item.entry), self._new_bucket(item.entry))
            bucket["keyword"] = max(bucket["keyword"], item.score)
            bucket["reason"]["keyword"] = item.reason
        for item in vector_hits:
            bucket = merged.setdefault(self._key(item.entry), self._new_bucket(item.entry))
            bucket["vector"] = max(bucket["vector"], item.score)
            bucket["reason"]["vector"] = item.reason

        ranked: list[FusionRankedHit] = []
        for _, bucket in merged.items():
            metadata_score = float(bucket["metadata"])
            keyword_score = float(bucket["keyword"])
            vector_score = float(bucket["vector"])
            final_score = self._final_score(metadata=metadata_score, keyword=keyword_score, vector=vector_score)
            detail = {
                "metadata_boost": round(metadata_score, 4),
                "keyword": round(keyword_score, 4),
                "vector": round(vector_score, 4),
            }
            hit_reason = self._pick_reason(bucket["reason"], detail)
            ranked.append(
                FusionRankedHit(
                    entry=bucket["entry"],
                    score=round(final_score, 4),
                    score_detail=detail,
                    hit_reason=hit_reason,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[: max(1, top_k)]

    @staticmethod
    def _new_bucket(entry: RetrievalIndexEntry) -> dict:
        return {
            "entry": entry,
            "metadata": 0.0,
            "keyword": 0.0,
            "vector": 0.0,
            "reason": {},
        }

    @staticmethod
    def _key(entry: RetrievalIndexEntry) -> str:
        return f"{entry.object_type.value}:{entry.object_id}"

    @staticmethod
    def _final_score(*, metadata: float, keyword: float, vector: float) -> float:
        weights = {"metadata": 0.2, "keyword": 0.5, "vector": 0.3}
        active_sum = 0.0
        weighted = 0.0
        if metadata > 0:
            active_sum += weights["metadata"]
            weighted += weights["metadata"] * metadata
        if keyword > 0:
            active_sum += weights["keyword"]
            weighted += weights["keyword"] * keyword
        if vector > 0:
            active_sum += weights["vector"]
            weighted += weights["vector"] * vector
        if active_sum == 0:
            return 0.0
        return min(1.0, weighted / active_sum)

    @staticmethod
    def _pick_reason(reasons: dict, detail: dict[str, float]) -> str:
        winner = max(detail, key=detail.get)
        if winner == "metadata_boost":
            return reasons.get("metadata") or "元数据匹配"
        if winner == "keyword":
            return reasons.get("keyword") or "关键词匹配"
        return reasons.get("vector") or "语义匹配"
