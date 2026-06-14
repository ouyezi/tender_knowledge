from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.module_assembly_suggestion import (
    ModuleAssemblySuggestion,
    ModuleAssemblySuggestionStatus,
)
from src.models.tender_requirement_context import TenderRequirementContext
from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus, RetrievalObjectType
from src.models.retrieval_trace import RetrievalIntent
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.schemas.retrieval import RetrievalRequest
from src.services.retrieval.match_score_calculator import MatchScoreCalculator
from src.services.retrieval.ranking.conflict_detector import ConflictDetector
from src.services.retrieval.recall.structure_recall import StructureRecallService
from src.services.retrieval.strategy_seed import DEFAULT_STRATEGY_CONFIG
from src.services.retrieval.trace.retrieval_trace_service import RetrievalTraceService


class ModuleSuggestionAdoptionError(Exception):
    def __init__(self, message: str, *, code: str = "VALIDATION"):
        self.code = code
        super().__init__(message)


class ModuleSuggestionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.structure_recall = StructureRecallService(db)
        self.conflict_detector = ConflictDetector()
        self.trace_service = RetrievalTraceService(db)

    def _load_requirement_context(
        self,
        *,
        kb_id: UUID,
        requirement_context_id: UUID | None,
    ) -> TenderRequirementContext | None:
        if requirement_context_id is None:
            return None
        return (
            self.db.query(TenderRequirementContext)
            .filter(
                TenderRequirementContext.kb_id == kb_id,
                TenderRequirementContext.requirement_context_id == requirement_context_id,
            )
            .one_or_none()
        )

    @staticmethod
    def _requirement_context_snapshot(row: TenderRequirementContext) -> dict[str, Any]:
        return {
            "requirement_context_id": str(row.requirement_context_id),
            "title": row.title,
            "outline_structure": row.outline_structure,
            "outline_nodes": row.outline_nodes,
            "score_points": row.score_points,
            "rejection_clauses": row.rejection_clauses,
            "format_requirements": row.format_requirements,
            "qualification_requirements": row.qualification_requirements,
            "response_clauses": row.response_clauses,
            "source_note": row.source_note,
            "status": row.status.value,
        }

    def create_suggestions(
        self,
        *,
        kb_id: UUID,
        request: RetrievalRequest,
        operator_id: str | None = None,
        requirement_context_id: UUID | None = None,
    ) -> dict:
        started_at = time.perf_counter()
        strategy_config = DEFAULT_STRATEGY_CONFIG
        suggestions: list[dict] = []
        saved_rows: list[ModuleAssemblySuggestion] = []

        requirement_context = self._load_requirement_context(
            kb_id=kb_id,
            requirement_context_id=requirement_context_id,
        )
        if requirement_context_id is not None and requirement_context is None:
            raise ModuleSuggestionAdoptionError(
                "tender requirement context not found",
                code="NOT_FOUND",
            )

        tender_context = request.tender_requirement_context
        rejection_clauses = tender_context.rejection_clauses
        tender_snapshot = tender_context.model_dump(mode="json")
        if requirement_context is not None:
            rejection_clauses = requirement_context.rejection_clauses
            tender_snapshot = self._requirement_context_snapshot(requirement_context)

        trace = self.trace_service.write_trace(
            kb_id=kb_id,
            intent=RetrievalIntent.module_suggestion,
            strategy_version_id=request.retrieval_options.strategy_version_id,
            request_snapshot=request.model_dump(mode="json"),
            stages={"module_suggestion": {"outline_count": len(request.outline_nodes)}},
            response_summary={"suggestion_count": 0},
            operator_id=operator_id,
            started_at_ms=started_at,
        )

        for node in request.outline_nodes:
            recall = self.structure_recall.recall(
                kb_id=kb_id,
                outline_nodes=[node.model_dump()],
                product_category_ids=[str(item) for item in request.product_category_ids],
                top_k=request.retrieval_options.top_k,
            )
            template_rows = (
                self.db.query(TemplateChapter)
                .filter(
                    TemplateChapter.kb_id == kb_id,
                    TemplateChapter.status == TemplateChapterStatus.published,
                )
                .all()
            )
            if request.product_category_ids:
                request_set = {str(item) for item in request.product_category_ids}
                template_rows = [
                    row
                    for row in template_rows
                    if request_set.intersection({str(item) for item in (row.product_category_ids or [])})
                ]
            conflict_ids, risk_flags = self.conflict_detector.detect(
                template_chapters=template_rows,
                rejection_clauses=rejection_clauses,
            )
            filtered_template_ids = [
                str(item) for item in recall.matched_template_chapter_ids if str(item) not in conflict_ids
            ]

            score_result = MatchScoreCalculator(strategy_config.get("match_score_weights", {})).calculate(
                product_category_score=1.0 if request.product_category_ids else 0.8,
                chapter_taxonomy_score=recall.chapter_taxonomy_score,
                title_similarity_score=recall.title_similarity_score,
                level_order_score=recall.level_order_score,
                knowledge_coverage_score=self._knowledge_coverage(
                    kb_id=kb_id, product_category_ids=[str(item) for item in request.product_category_ids]
                ),
            )
            knowledge_ids = self._collect_knowledge_ids(
                kb_id=kb_id, product_category_ids=[str(item) for item in request.product_category_ids], top_k=3
            )
            row = ModuleAssemblySuggestion(
                kb_id=kb_id,
                trace_id=trace.trace_id,
                target_outline_node=node.model_dump(mode="json"),
                suggested_template_chapter_ids=filtered_template_ids,
                suggested_ku_ids=knowledge_ids["ku"],
                suggested_wiki_ids=knowledge_ids["wiki"],
                suggested_manual_asset_ids=knowledge_ids["manual_asset"],
                suggested_bid_outline_node_ids=[str(item) for item in recall.matched_outline_ids],
                suggested_chapter_pattern_ids=[str(item) for item in recall.matched_pattern_ids],
                organization_hint={"order": ["template_chapter", "ku", "wiki", "manual_asset"]},
                match_score=float(score_result["match_score"]),
                coverage_rate=float(score_result["coverage_rate"]),
                score_detail=score_result["score_detail"],
                score_point_coverage=[],
                rejection_risks=[],
                risk_flags=risk_flags,
                hit_reason="历史目录与模板章节匹配",
                knowledge_pack_snapshot=[],
                product_category_ids=[str(item) for item in request.product_category_ids],
                project_type=None,
                customer_type=None,
                tender_context_snapshot=tender_snapshot,
                requirement_context_id=requirement_context.requirement_context_id
                if requirement_context is not None
                else None,
            )
            self.db.add(row)
            self.db.flush()
            saved_rows.append(row)
            suggestions.append(
                {
                    "suggestion_id": str(row.suggestion_id),
                    "target_outline_node": row.target_outline_node,
                    "suggested_template_chapter_ids": row.suggested_template_chapter_ids,
                    "suggested_ku_ids": row.suggested_ku_ids,
                    "suggested_wiki_ids": row.suggested_wiki_ids,
                    "suggested_manual_asset_ids": row.suggested_manual_asset_ids,
                    "suggested_bid_outline_node_ids": row.suggested_bid_outline_node_ids,
                    "suggested_chapter_pattern_ids": row.suggested_chapter_pattern_ids,
                    "organization_hint": row.organization_hint,
                    "match_score": row.match_score,
                    "coverage_rate": row.coverage_rate,
                    "score_detail": row.score_detail,
                    "score_point_coverage": row.score_point_coverage,
                    "rejection_risks": row.rejection_risks,
                    "risk_flags": row.risk_flags,
                    "hit_reason": row.hit_reason,
                    "available_ku_count": len(row.suggested_ku_ids),
                    "available_wiki_count": len(row.suggested_wiki_ids),
                    "knowledge_pack_items": [],
                }
            )

        trace.response_summary = {"suggestion_count": len(suggestions)}
        self.db.flush()
        return {
            "trace_id": str(trace.trace_id),
            "module_suggestions": suggestions,
            "missing_chapters": [],
            "latency_ms": trace.latency_ms or max(1, int((time.perf_counter() - started_at) * 1000)),
        }

    def get_suggestion(self, *, kb_id: UUID, suggestion_id: UUID) -> ModuleAssemblySuggestion | None:
        return (
            self.db.query(ModuleAssemblySuggestion)
            .filter(
                ModuleAssemblySuggestion.kb_id == kb_id,
                ModuleAssemblySuggestion.suggestion_id == suggestion_id,
            )
            .one_or_none()
        )

    def adopt(
        self,
        *,
        kb_id: UUID,
        suggestion_id: UUID,
        status: str,
        adoption_reason: str | None,
        operator_id: str | None = None,
    ) -> ModuleAssemblySuggestion:
        if status not in {
            ModuleAssemblySuggestionStatus.adopted.value,
            ModuleAssemblySuggestionStatus.rejected.value,
        }:
            raise ModuleSuggestionAdoptionError("status must be adopted or rejected")

        row = self.get_suggestion(kb_id=kb_id, suggestion_id=suggestion_id)
        if row is None:
            raise ModuleSuggestionAdoptionError("module suggestion not found", code="SUGGESTION_NOT_FOUND")

        now = datetime.now(timezone.utc)
        row.status = ModuleAssemblySuggestionStatus(status)
        row.adoption_reason = adoption_reason
        row.adopted_by = operator_id
        row.adopted_at = now if status == ModuleAssemblySuggestionStatus.adopted.value else None
        self.db.flush()
        return row

    def _collect_knowledge_ids(self, *, kb_id: UUID, product_category_ids: list[str], top_k: int) -> dict[str, list[str]]:
        q = self.db.query(RetrievalIndexEntry).filter(
            RetrievalIndexEntry.kb_id == kb_id,
            RetrievalIndexEntry.status == RetrievalIndexStatus.published,
        )
        rows = q.all()
        request_set = set(product_category_ids)
        if request_set:
            rows = [
                row
                for row in rows
                if request_set.intersection({str(item) for item in (row.product_category_ids or [])})
            ]
        grouped: dict[str, list[str]] = {"ku": [], "wiki": [], "manual_asset": []}
        for row in rows:
            key = row.object_type.value
            if key not in grouped:
                continue
            grouped[key].append(str(row.object_id))
        return {k: v[:top_k] for k, v in grouped.items()}

    def _knowledge_coverage(self, *, kb_id: UUID, product_category_ids: list[str]) -> float:
        q = self.db.query(RetrievalIndexEntry).filter(
            RetrievalIndexEntry.kb_id == kb_id,
            RetrievalIndexEntry.status == RetrievalIndexStatus.published,
            RetrievalIndexEntry.object_type.in_(
                [RetrievalObjectType.ku, RetrievalObjectType.wiki, RetrievalObjectType.manual_asset]
            ),
        )
        rows = q.all()
        if not rows:
            return 0.0
        if not product_category_ids:
            return 1.0
        request_set = set(product_category_ids)
        matched = [
            row
            for row in rows
            if request_set.intersection({str(item) for item in (row.product_category_ids or [])})
        ]
        return round(min(1.0, len(matched) / len(rows)), 4)
