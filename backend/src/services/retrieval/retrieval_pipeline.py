from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.schemas.retrieval import RetrievalRequest
from src.services.retrieval.knowledge_pack_builder import KnowledgePackBuilder
from src.services.retrieval.ranking.fusion_ranker import FusionRanker
from src.services.retrieval.recall.keyword_recall import KeywordRecallService
from src.services.retrieval.recall.metadata_recall import MetadataRecallService
from src.services.retrieval.recall.vector_recall import VectorRecallService


@dataclass(slots=True)
class RetrievalPipelineResult:
    items: list[dict]
    stages: dict
    total: int


class RetrievalPipeline:
    def __init__(self, metadata_recall: MetadataRecallService, keyword_recall: KeywordRecallService, vector_recall: VectorRecallService) -> None:
        self.metadata_recall = metadata_recall
        self.keyword_recall = keyword_recall
        self.vector_recall = vector_recall
        self.fusion_ranker = FusionRanker()
        self.pack_builder = KnowledgePackBuilder()

    def execute(self, *, kb_id: UUID, request: RetrievalRequest) -> RetrievalPipelineResult:
        top_k = max(1, request.retrieval_options.top_k)
        metadata_hits = self.metadata_recall.recall(kb_id=kb_id, request=request, top_k=top_k * 2)
        keyword_hits = []
        if request.retrieval_options.enable_bm25:
            keyword_hits = self.keyword_recall.recall(
                kb_id=kb_id,
                query=request.query,
                top_k=top_k * 2,
            )
        vector_result = self.vector_recall.recall(
            kb_id=kb_id,
            query=request.query,
            top_k=top_k * 2,
        ) if request.retrieval_options.enable_vector else None
        vector_hits = vector_result.hits if vector_result else []
        ranked_hits = self.fusion_ranker.rank(
            metadata_hits=metadata_hits,
            keyword_hits=keyword_hits,
            vector_hits=vector_hits,
            top_k=top_k,
        )
        items = [
            self.pack_builder.build(
                item.entry,
                score=item.score,
                score_detail=item.score_detail,
                hit_reason=item.hit_reason,
            )
            for item in ranked_hits
        ]
        stages = {
            "metadata_recall": {"hit_count": len(metadata_hits)},
            "keyword_recall": {"hit_count": len(keyword_hits)},
            "vector_recall": {
                "hit_count": len(vector_hits),
                "vector_disabled_reason": (
                    vector_result.vector_disabled_reason if vector_result else None
                ),
            },
            "fusion_ranker": {"hit_count": len(ranked_hits)},
        }
        return RetrievalPipelineResult(items=items, stages=stages, total=len(items))
