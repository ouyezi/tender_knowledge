from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.retrieval_eval_case import RetrievalEvalCase, RetrievalEvalCaseStatus
from src.models.retrieval_eval_run import RetrievalEvalRun, RetrievalEvalRunStatus
from src.models.retrieval_eval_set import RetrievalEvalSet
from src.models.retrieval_strategy_version import RetrievalStrategyVersion
from src.schemas.retrieval import RetrievalIntent, RetrievalOptions, RetrievalRequest, ReturnOptions
from src.services.retrieval.eval.metrics import compute_metrics
from src.services.retrieval.retrieval_service import RetrievalService


class RetrievalEvalRunner:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.retrieval = RetrievalService(db)

    def run(
        self,
        *,
        kb_id: UUID,
        eval_set_id: UUID,
        strategy_version_id: UUID,
        baseline_strategy_version_id: UUID | None,
        k: int,
        metrics: list[str] | None,
        triggered_by: str | None,
    ) -> RetrievalEvalRun:
        self._ensure_strategy_exists(kb_id=kb_id, strategy_version_id=strategy_version_id)
        if baseline_strategy_version_id is not None:
            self._ensure_strategy_exists(kb_id=kb_id, strategy_version_id=baseline_strategy_version_id)
        self._ensure_eval_set_exists(kb_id=kb_id, eval_set_id=eval_set_id)
        self._ensure_not_running(kb_id=kb_id, eval_set_id=eval_set_id, strategy_version_id=strategy_version_id)

        cases = (
            self.db.query(RetrievalEvalCase)
            .filter(
                RetrievalEvalCase.kb_id == kb_id,
                RetrievalEvalCase.eval_set_id == eval_set_id,
                RetrievalEvalCase.status == RetrievalEvalCaseStatus.confirmed,
                RetrievalEvalCase.confirmed_at.is_not(None),
            )
            .all()
        )
        if not cases:
            raise ValueError("EVAL_SET_EMPTY")

        run = RetrievalEvalRun(
            kb_id=kb_id,
            eval_set_id=eval_set_id,
            strategy_version_id=strategy_version_id,
            baseline_strategy_version_id=baseline_strategy_version_id,
            status=RetrievalEvalRunStatus.running,
            started_at=datetime.now(timezone.utc),
            triggered_by=triggered_by,
        )
        self.db.add(run)
        self.db.flush()

        selected = set(metrics or ["recall_at_k", "precision_at_k", "mrr", "ndcg"])
        current_metrics = self._compute_for_strategy(
            kb_id=kb_id,
            strategy_version_id=strategy_version_id,
            cases=cases,
            k=max(1, k),
            metric_filter=selected,
        )
        run.metrics = current_metrics
        if baseline_strategy_version_id is not None:
            baseline_metrics = self._compute_for_strategy(
                kb_id=kb_id,
                strategy_version_id=baseline_strategy_version_id,
                cases=cases,
                k=max(1, k),
                metric_filter=selected,
            )
            run.comparison_metrics = {
                f"{name}_delta": round(current_metrics.get(name, 0.0) - baseline_metrics.get(name, 0.0), 4)
                for name in current_metrics
            }
        else:
            run.comparison_metrics = None
        run.status = RetrievalEvalRunStatus.success
        run.finished_at = datetime.now(timezone.utc)
        self.db.flush()
        return run

    def get_run(self, *, kb_id: UUID, eval_run_id: UUID) -> RetrievalEvalRun | None:
        return (
            self.db.query(RetrievalEvalRun)
            .filter(RetrievalEvalRun.kb_id == kb_id, RetrievalEvalRun.eval_run_id == eval_run_id)
            .one_or_none()
        )

    def _compute_for_strategy(
        self,
        *,
        kb_id: UUID,
        strategy_version_id: UUID,
        cases: list[RetrievalEvalCase],
        k: int,
        metric_filter: set[str],
    ) -> dict[str, float]:
        totals: dict[str, float] = {
            "recall_at_k": 0.0,
            "precision_at_k": 0.0,
            "mrr": 0.0,
            "ndcg": 0.0,
            "adoption_rate": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0,
            "sourced_result_rate": 0.0,
        }

        for case in cases:
            request = RetrievalRequest(
                query=case.query,
                intent=RetrievalIntent(case.intent.value),
                product_category_ids=[UUID(item) for item in (case.product_category_ids or [])],
                chapter_taxonomy_ids=[UUID(item) for item in (case.chapter_taxonomy_ids or [])],
                retrieval_options=RetrievalOptions(strategy_version_id=strategy_version_id, top_k=k),
                return_options=ReturnOptions(
                    include_trace=False,
                    include_score_detail=False,
                    include_conflict_flags=False,
                    include_knowledge_pack=False,
                ),
            )
            result = self.retrieval.search(kb_id=kb_id, request=request, operator_id="eval-runner")
            predicted_ids = [str(item.get("object_id")) for item in result.get("items", []) if item.get("object_id")]
            per_case = compute_metrics(
                expected_object_ids=[str(item) for item in (case.expected_object_ids or [])],
                predicted_object_ids=predicted_ids,
                k=k,
            )
            for name, value in per_case.items():
                totals[name] += value
            totals["sourced_result_rate"] += 1.0 if predicted_ids else 0.0

        count = len(cases)
        averages = {name: round(value / count, 4) for name, value in totals.items()}
        return {name: value for name, value in averages.items() if name in metric_filter}

    def _ensure_strategy_exists(self, *, kb_id: UUID, strategy_version_id: UUID) -> None:
        exists = (
            self.db.query(RetrievalStrategyVersion.strategy_version_id)
            .filter(
                RetrievalStrategyVersion.kb_id == kb_id,
                RetrievalStrategyVersion.strategy_version_id == strategy_version_id,
            )
            .first()
        )
        if exists is None:
            raise ValueError("STRATEGY_VERSION_NOT_FOUND")

    def _ensure_eval_set_exists(self, *, kb_id: UUID, eval_set_id: UUID) -> None:
        exists = (
            self.db.query(RetrievalEvalSet.eval_set_id)
            .filter(RetrievalEvalSet.kb_id == kb_id, RetrievalEvalSet.eval_set_id == eval_set_id)
            .first()
        )
        if exists is None:
            raise ValueError("EVAL_SET_NOT_FOUND")

    def _ensure_not_running(self, *, kb_id: UUID, eval_set_id: UUID, strategy_version_id: UUID) -> None:
        running = (
            self.db.query(RetrievalEvalRun.eval_run_id)
            .filter(
                RetrievalEvalRun.kb_id == kb_id,
                RetrievalEvalRun.eval_set_id == eval_set_id,
                RetrievalEvalRun.strategy_version_id == strategy_version_id,
                RetrievalEvalRun.status == RetrievalEvalRunStatus.running,
            )
            .first()
        )
        if running is not None:
            raise ValueError("EVAL_RUN_IN_PROGRESS")
