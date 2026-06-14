from __future__ import annotations

import time
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.models.knowledge_unit import KnowledgeUnit
from src.models.manual_asset import ManualAsset
from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus
from src.models.retrieval_strategy_version import RetrievalStrategyVersion
from src.models.retrieval_trace import RetrievalIntent, RetrievalTrace, RetrievalTraceStatus
from src.models.wiki import Wiki
from src.schemas.retrieval import RetrievalRequest
from src.services.retrieval.chapter_gap_diagnoser import ChapterGapDiagnoser
from src.services.retrieval.indexing.index_builder import IndexBuilder
from src.services.retrieval.match_score_calculator import MatchScoreCalculator
from src.services.retrieval.recall.keyword_recall import KeywordRecallService
from src.services.retrieval.recall.metadata_recall import MetadataRecallService
from src.services.retrieval.recall.structure_recall import StructureRecallService
from src.services.retrieval.recall.vector_recall import VectorRecallService
from src.services.retrieval.retrieval_pipeline import RetrievalPipeline
from src.services.retrieval.strategy_seed import DEFAULT_STRATEGY_CONFIG, seed_default_strategy
from src.services.retrieval.trace.retrieval_trace_service import RetrievalTraceService


class RetrievalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.structure_recall = StructureRecallService(db)
        self.trace_service = RetrievalTraceService(db)
        self.pipeline = RetrievalPipeline(
            metadata_recall=MetadataRecallService(db),
            keyword_recall=KeywordRecallService(db),
            vector_recall=VectorRecallService(db),
        )

    def search(self, *, kb_id: UUID, request: RetrievalRequest, operator_id: str | None = None) -> dict:
        started_at = time.perf_counter()
        strategy = self._resolve_strategy(kb_id=kb_id, strategy_version_id=request.retrieval_options.strategy_version_id)
        result = self.pipeline.execute(kb_id=kb_id, request=request)
        trace = self.trace_service.write_trace(
            kb_id=kb_id,
            intent=RetrievalIntent(request.intent.value),
            strategy_version_id=strategy.strategy_version_id if strategy else None,
            request_snapshot=request.model_dump(mode="json"),
            stages=result.stages,
            response_summary={"total": result.total},
            operator_id=operator_id,
            started_at_ms=started_at,
            status=RetrievalTraceStatus.success,
        )
        return {
            "trace_id": str(trace.trace_id),
            "intent": request.intent.value,
            "strategy_version_id": str(trace.strategy_version_id) if trace.strategy_version_id else None,
            "latency_ms": trace.latency_ms or max(1, int((time.perf_counter() - started_at) * 1000)),
            "items": result.items,
            "total": result.total,
        }

    def directory_match(self, *, kb_id: UUID, request: RetrievalRequest, operator_id: str | None = None) -> dict:
        started_at = time.perf_counter()
        strategy = self._resolve_strategy(kb_id=kb_id, strategy_version_id=request.retrieval_options.strategy_version_id)
        config = strategy.config or DEFAULT_STRATEGY_CONFIG
        recall_result = self.structure_recall.recall(
            kb_id=kb_id,
            outline_nodes=[item.model_dump() for item in request.outline_nodes],
            product_category_ids=[str(item) for item in request.product_category_ids],
            top_k=request.retrieval_options.top_k,
        )
        score_calculator = MatchScoreCalculator(config.get("match_score_weights", {}))
        knowledge_coverage_score = self._knowledge_coverage_score(
            kb_id=kb_id, product_category_ids=[str(item) for item in request.product_category_ids]
        )
        score_result = score_calculator.calculate(
            product_category_score=self._category_score(request.product_category_ids, recall_result),
            chapter_taxonomy_score=recall_result.chapter_taxonomy_score,
            title_similarity_score=recall_result.title_similarity_score,
            level_order_score=recall_result.level_order_score,
            knowledge_coverage_score=knowledge_coverage_score,
        )
        gap_diagnoser = ChapterGapDiagnoser(config.get("gap_threshold", {}))
        missing_chapters = gap_diagnoser.diagnose(
            matched_pattern_ids=recall_result.matched_pattern_ids,
            candidate_patterns=recall_result.candidate_patterns,
        )
        directory_match_payload = {
            "match_score": score_result["match_score"],
            "coverage_rate": score_result["coverage_rate"],
            "score_detail": score_result["score_detail"],
            "matched_outline_ids": [str(item) for item in recall_result.matched_outline_ids],
            "matched_template_chapter_ids": [str(item) for item in recall_result.matched_template_chapter_ids],
            "matched_pattern_ids": [str(item) for item in recall_result.matched_pattern_ids],
            "missing_chapters": missing_chapters,
        }
        trace = self.trace_service.write_trace(
            kb_id=kb_id,
            intent=RetrievalIntent.directory_match,
            strategy_version_id=strategy.strategy_version_id if strategy else None,
            request_snapshot=request.model_dump(mode="json"),
            stages={
                "structure_recall": {
                    "outline_count": len(recall_result.matched_outline_ids),
                    "template_chapter_count": len(recall_result.matched_template_chapter_ids),
                    "pattern_count": len(recall_result.matched_pattern_ids),
                }
            },
            response_summary={
                "match_score": score_result["match_score"],
                "coverage_rate": score_result["coverage_rate"],
                "missing_chapter_count": len(missing_chapters),
            },
            operator_id=operator_id,
            started_at_ms=started_at,
        )
        return {
            "trace_id": str(trace.trace_id),
            "intent": RetrievalIntent.directory_match.value,
            "strategy_version_id": str(trace.strategy_version_id) if trace.strategy_version_id else None,
            "latency_ms": trace.latency_ms or max(1, int((time.perf_counter() - started_at) * 1000)),
            "directory_match": directory_match_payload,
            "total": len(recall_result.matched_outline_ids)
            + len(recall_result.matched_template_chapter_ids)
            + len(recall_result.matched_pattern_ids),
        }

    def list_traces(
        self,
        *,
        kb_id: UUID,
        intent: RetrievalIntent | None = None,
        status: RetrievalTraceStatus | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        operator_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        query = self.db.query(RetrievalTrace).filter(RetrievalTrace.kb_id == kb_id)
        if intent is not None:
            query = query.filter(RetrievalTrace.intent == RetrievalIntent(intent.value))
        if status is not None:
            query = query.filter(RetrievalTrace.status == status)
        if from_dt is not None:
            query = query.filter(RetrievalTrace.created_at >= from_dt)
        if to_dt is not None:
            query = query.filter(RetrievalTrace.created_at <= to_dt)
        if operator_id:
            query = query.filter(RetrievalTrace.operator_id == operator_id)
        total = query.count()
        rows = (
            query.order_by(RetrievalTrace.created_at.desc())
            .offset(max(0, page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [
                {
                    "trace_id": str(row.trace_id),
                    "intent": row.intent.value,
                    "strategy_version_id": str(row.strategy_version_id) if row.strategy_version_id else None,
                    "status": row.status.value,
                    "latency_ms": row.latency_ms or 0,
                    "result_count": int((row.response_summary or {}).get("total", 0)),
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_trace(self, *, kb_id: UUID, trace_id: UUID) -> dict | None:
        row = (
            self.db.query(RetrievalTrace)
            .filter(RetrievalTrace.kb_id == kb_id, RetrievalTrace.trace_id == trace_id)
            .one_or_none()
        )
        if row is None:
            return None
        return {
            "trace_id": str(row.trace_id),
            "intent": row.intent.value,
            "strategy_version_id": str(row.strategy_version_id) if row.strategy_version_id else None,
            "status": row.status.value,
            "latency_ms": row.latency_ms or 0,
            "request_snapshot": row.request_snapshot or {},
            "stages": row.stages or {},
            "response_summary": row.response_summary or {},
            "error_message": row.error_message,
            "operator_id": row.operator_id,
            "created_at": row.created_at.isoformat(),
        }

    def rebuild_index(self, *, kb_id: UUID, object_types: list[str] | None = None, force_reembed: bool = False) -> dict:
        _ = force_reembed
        requested = set(object_types or [])
        index_builder = IndexBuilder(self.db)
        counts = {"ku": 0, "wiki": 0, "manual_asset": 0}
        if not requested or "ku" in requested:
            for row in self.db.query(KnowledgeUnit).filter(KnowledgeUnit.kb_id == kb_id).all():
                index_builder.upsert_from_ku(row)
                counts["ku"] += 1
        if not requested or "wiki" in requested:
            for row in self.db.query(Wiki).filter(Wiki.kb_id == kb_id).all():
                index_builder.upsert_from_wiki(row)
                counts["wiki"] += 1
        if not requested or "manual_asset" in requested:
            for row in self.db.query(ManualAsset).filter(ManualAsset.kb_id == kb_id).all():
                index_builder.upsert_from_manual_asset(row)
                counts["manual_asset"] += 1
        self.db.flush()
        return {"task_id": str(uuid4()), "status": "queued", "stats": counts}

    def _resolve_strategy(self, *, kb_id: UUID, strategy_version_id: UUID | None) -> RetrievalStrategyVersion:
        if strategy_version_id:
            strategy = (
                self.db.query(RetrievalStrategyVersion)
                .filter(
                    RetrievalStrategyVersion.kb_id == kb_id,
                    RetrievalStrategyVersion.strategy_version_id == strategy_version_id,
                )
                .one_or_none()
            )
            if strategy:
                return strategy
            raise ValueError("STRATEGY_VERSION_NOT_FOUND")
        strategy = (
            self.db.query(RetrievalStrategyVersion)
            .filter(RetrievalStrategyVersion.kb_id == kb_id, RetrievalStrategyVersion.is_active.is_(True))
            .one_or_none()
        )
        if strategy:
            return strategy
        strategy = seed_default_strategy(self.db, kb_id=kb_id)
        self.db.commit()
        self.db.refresh(strategy)
        return strategy

    def _knowledge_coverage_score(self, *, kb_id: UUID, product_category_ids: list[str]) -> float:
        rows = (
            self.db.query(RetrievalIndexEntry)
            .filter(
                RetrievalIndexEntry.kb_id == kb_id,
                RetrievalIndexEntry.status == RetrievalIndexStatus.published,
            )
            .all()
        )
        if not rows:
            return 0.0
        if not product_category_ids:
            return 1.0
        request_set = set(product_category_ids)
        hits = [
            row
            for row in rows
            if request_set.intersection({str(item) for item in (row.product_category_ids or [])})
        ]
        return round(min(1.0, len(hits) / max(1, len(rows))), 4)

    @staticmethod
    def _category_score(product_category_ids: list[UUID], recall_result) -> float:
        if not product_category_ids:
            return 1.0
        category_hits = len(recall_result.matched_outline_ids) + len(recall_result.matched_template_chapter_ids)
        return min(1.0, category_hits / max(1, len(product_category_ids)))
