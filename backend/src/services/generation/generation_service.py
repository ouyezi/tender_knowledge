from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.chapter_draft import ChapterDraft, DraftOutcomeStatus
from src.models.generation_snapshot import GenerationSnapshot
from src.models.generation_task import GenerationTask, GenerationTaskStatus
from src.models.module_assembly_suggestion import ModuleAssemblySuggestion
from src.models.tender_requirement_context import TenderRequirementContext
from src.models.template_chapter import TemplateChapter
from src.schemas.generation import (
    GenerationDraftCreateRequest,
    GenerationDraftRegenerateRequest,
    UserChapterSelection,
)
from src.services.generation.citation_binder import CitationBinder
from src.services.generation.compliance_checker import ComplianceChecker
from src.services.generation.conditional_chapter_evaluator import ConditionalChapterEvaluator
from src.services.generation.input_priority_resolver import InputPriorityResolver
from src.services.generation.prompt_builder import PromptBuilder
from src.services.generation.snapshot_writer import SnapshotWriter, build_retrieval_trace_summary
from src.services.generation.variable_resolver import GenerationPreflightError, epic6_draft_preflight
from src.services.llm_client import chat_completion, is_llm_available
from src.services.retrieval.module_suggestion.module_suggestion_service import ModuleSuggestionService
from src.services.retrieval.ranking.conflict_detector import ConflictDetector


class GenerationServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int = 422):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def serialize_chapter_draft(row: ChapterDraft, *, full: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "draft_id": str(row.draft_id),
        "task_id": str(row.task_id),
        "snapshot_id": str(row.snapshot_id),
        "target_outline_node": row.target_outline_node,
        "outcome_status": row.outcome_status.value,
        "version_tag": row.version_tag,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat(),
    }
    if full:
        payload.update(
            {
                "paragraphs": row.paragraphs,
                "conflict_hints": row.conflict_hints,
                "missing_material_hints": row.missing_material_hints,
            }
        )
    return payload


def serialize_generation_snapshot(row: GenerationSnapshot, *, full: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "snapshot_id": str(row.snapshot_id),
        "task_id": str(row.task_id),
        "requirement_context_id": str(row.requirement_context_id),
        "target_outline_node": row.target_outline_node,
        "prompt_version": row.prompt_version,
        "result_version": row.result_version,
        "created_at": row.created_at.isoformat(),
    }
    if full:
        payload.update(
            {
                "requirement_context_snapshot": row.requirement_context_snapshot,
                "suggestion_id": str(row.suggestion_id) if row.suggestion_id else None,
                "suggestion_snapshot": row.suggestion_snapshot,
                "used_ku_ids": row.used_ku_ids,
                "used_wiki_ids": row.used_wiki_ids,
                "used_template_chapter_ids": row.used_template_chapter_ids,
                "used_manual_asset_ids": row.used_manual_asset_ids,
                "variable_inputs": row.variable_inputs,
                "retrieval_trace_summary": row.retrieval_trace_summary,
                "conflict_hints": row.conflict_hints,
                "missing_material_hints": row.missing_material_hints,
                "input_priority_layers": row.input_priority_layers,
            }
        )
    return payload


class GenerationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.resolver = InputPriorityResolver()
        self.chapter_evaluator = ConditionalChapterEvaluator()
        self.compliance_checker = ComplianceChecker()
        self.prompt_builder = PromptBuilder()
        self.citation_binder = CitationBinder()
        self.conflict_detector = ConflictDetector()
        self.snapshot_writer = SnapshotWriter(db)

    def create_draft_task(
        self,
        *,
        kb_id: UUID,
        body: GenerationDraftCreateRequest,
        operator_id: str | None,
        trace_id: UUID | None,
    ) -> GenerationTask:
        try:
            resolved_variables = epic6_draft_preflight(
                self.db,
                kb_id=kb_id,
                requirement_context_id=body.requirement_context_id,
                suggestion_id=body.suggestion_id,
                variable_values=body.variable_values,
                confirm_adoption=body.confirm_adoption,
                user_chapter_selections=body.user_chapter_selections,
            )
        except GenerationPreflightError:
            raise

        request_snapshot = body.model_dump(mode="json")
        request_snapshot["resolved_variables"] = resolved_variables
        task = GenerationTask(
            kb_id=kb_id,
            requirement_context_id=body.requirement_context_id,
            suggestion_id=body.suggestion_id,
            target_outline_node=body.target_outline_node.model_dump(mode="json"),
            status=GenerationTaskStatus.pending,
            request_snapshot=request_snapshot,
            trace_id=trace_id,
            created_by=operator_id,
        )
        self.db.add(task)
        self.db.flush()
        return task

    def accept_draft(self, *, kb_id: UUID, draft_id: UUID, operator_id: str | None) -> ChapterDraft:
        draft = self.get_draft(kb_id=kb_id, draft_id=draft_id)
        if draft is None:
            raise GenerationServiceError("chapter draft not found", code="NOT_FOUND", status_code=404)

        now = datetime.now(timezone.utc)
        draft.outcome_status = DraftOutcomeStatus.accepted
        draft.outcome_by = operator_id
        draft.outcome_at = now
        draft.is_active = True

        others = (
            self.db.query(ChapterDraft)
            .filter(
                ChapterDraft.kb_id == kb_id,
                ChapterDraft.draft_id != draft_id,
                ChapterDraft.outcome_status == DraftOutcomeStatus.accepted,
            )
            .all()
        )
        for other in others:
            if other.target_outline_node == draft.target_outline_node:
                other.is_active = False

        self.db.flush()
        return draft

    def discard_draft(self, *, kb_id: UUID, draft_id: UUID, operator_id: str | None) -> ChapterDraft:
        draft = self.get_draft(kb_id=kb_id, draft_id=draft_id)
        if draft is None:
            raise GenerationServiceError("chapter draft not found", code="NOT_FOUND", status_code=404)

        now = datetime.now(timezone.utc)
        draft.outcome_status = DraftOutcomeStatus.discarded
        draft.outcome_by = operator_id
        draft.outcome_at = now
        draft.is_active = False
        self.db.flush()
        return draft

    def regenerate_draft(
        self,
        *,
        kb_id: UUID,
        draft_id: UUID,
        body: GenerationDraftRegenerateRequest,
        operator_id: str | None,
        trace_id: UUID | None,
    ) -> GenerationTask:
        draft = self.get_draft(kb_id=kb_id, draft_id=draft_id)
        if draft is None:
            raise GenerationServiceError("chapter draft not found", code="NOT_FOUND", status_code=404)

        task = self.db.get(GenerationTask, draft.task_id)
        if task is None or task.kb_id != kb_id:
            raise GenerationServiceError("generation task not found", code="NOT_FOUND", status_code=404)

        snapshot = dict(task.request_snapshot or {})
        variable_values = dict(snapshot.get("variable_values") or {})
        if body.variable_values:
            variable_values.update(body.variable_values)

        user_chapter_selections = snapshot.get("user_chapter_selections") or []
        if body.user_chapter_selections is not None:
            user_chapter_selections = [
                item.model_dump(mode="json") for item in body.user_chapter_selections
            ]

        next_version_tag = self._next_version_tag(
            kb_id=kb_id,
            target_outline_node=draft.target_outline_node,
        )

        create_body = GenerationDraftCreateRequest(
            requirement_context_id=task.requirement_context_id,
            suggestion_id=task.suggestion_id,
            target_outline_node=task.target_outline_node,
            product_category_ids=snapshot.get("product_category_ids") or [],
            variable_values=variable_values,
            user_chapter_selections=[
                UserChapterSelection(**item) for item in user_chapter_selections
            ],
            manual_asset_compliance=snapshot.get("manual_asset_compliance") or [],
            confirm_adoption=bool(snapshot.get("confirm_adoption", False)),
            regenerate_from_draft_id=draft_id,
        )
        new_task = self.create_draft_task(
            kb_id=kb_id,
            body=create_body,
            operator_id=operator_id,
            trace_id=trace_id,
        )
        new_task.request_snapshot = {
            **new_task.request_snapshot,
            "version_tag": next_version_tag,
            "regenerate_from_draft_id": str(draft_id),
        }
        self.db.flush()
        return new_task

    def get_draft(self, *, kb_id: UUID, draft_id: UUID) -> ChapterDraft | None:
        return (
            self.db.query(ChapterDraft)
            .filter(ChapterDraft.kb_id == kb_id, ChapterDraft.draft_id == draft_id)
            .one_or_none()
        )

    def _next_version_tag(self, *, kb_id: UUID, target_outline_node: dict[str, Any]) -> str:
        rows = self.db.query(ChapterDraft).filter(ChapterDraft.kb_id == kb_id).all()
        max_num = 0
        for row in rows:
            if row.target_outline_node != target_outline_node:
                continue
            match = re.match(r"^v(\d+)$", row.version_tag)
            if match:
                max_num = max(max_num, int(match.group(1)))
        return f"v{max_num + 1}"

    def list_drafts(
        self,
        *,
        kb_id: UUID,
        target_title: str | None = None,
        requirement_context_id: UUID | None = None,
        outcome_status: DraftOutcomeStatus | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ChapterDraft], int]:
        query = self.db.query(ChapterDraft).filter(ChapterDraft.kb_id == kb_id)
        if requirement_context_id is not None:
            query = query.filter(ChapterDraft.requirement_context_id == requirement_context_id)
        if outcome_status is not None:
            query = query.filter(ChapterDraft.outcome_status == outcome_status)
        if is_active is not None:
            query = query.filter(ChapterDraft.is_active == is_active)
        if target_title:
            query = query.filter(
                ChapterDraft.target_outline_node["title"].as_string().ilike(f"%{target_title}%")
            )
        total = query.count()
        offset = max(page - 1, 0) * page_size
        rows = (
            query.order_by(ChapterDraft.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return rows, total

    def get_snapshot(self, *, kb_id: UUID, snapshot_id: UUID) -> GenerationSnapshot | None:
        return (
            self.db.query(GenerationSnapshot)
            .filter(
                GenerationSnapshot.kb_id == kb_id,
                GenerationSnapshot.snapshot_id == snapshot_id,
            )
            .one_or_none()
        )

    def list_snapshots(
        self,
        *,
        kb_id: UUID,
        requirement_context_id: UUID | None = None,
        target_title: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[GenerationSnapshot], int]:
        query = self.db.query(GenerationSnapshot).filter(GenerationSnapshot.kb_id == kb_id)
        if requirement_context_id is not None:
            query = query.filter(GenerationSnapshot.requirement_context_id == requirement_context_id)
        if target_title:
            query = query.filter(
                GenerationSnapshot.target_outline_node["title"].as_string().ilike(f"%{target_title}%")
            )
        if from_dt is not None:
            query = query.filter(GenerationSnapshot.created_at >= from_dt)
        if to_dt is not None:
            query = query.filter(GenerationSnapshot.created_at <= to_dt)
        total = query.count()
        offset = max(page - 1, 0) * page_size
        rows = (
            query.order_by(GenerationSnapshot.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return rows, total

    def run_task(self, task_id: UUID) -> None:
        task = self.db.get(GenerationTask, task_id)
        if task is None:
            raise GenerationServiceError("generation task not found", code="NOT_FOUND", status_code=404)

        task.status = GenerationTaskStatus.running
        task.started_at = datetime.now(timezone.utc)
        task.error_code = None
        task.error_message = None
        self.db.flush()

        try:
            if not is_llm_available():
                raise GenerationServiceError(
                    "LLM service is unavailable",
                    code="LLM_UNAVAILABLE",
                    status_code=503,
                )
            context = (
                self.db.query(TenderRequirementContext)
                .filter(
                    TenderRequirementContext.kb_id == task.kb_id,
                    TenderRequirementContext.requirement_context_id == task.requirement_context_id,
                )
                .one_or_none()
            )
            if context is None:
                raise GenerationServiceError("tender requirement context not found", code="NOT_FOUND", status_code=404)

            suggestion = None
            if task.suggestion_id is not None:
                suggestion = ModuleSuggestionService(self.db).get_suggestion(
                    kb_id=task.kb_id,
                    suggestion_id=task.suggestion_id,
                )
                if suggestion is None:
                    raise GenerationServiceError("module suggestion not found", code="NOT_FOUND", status_code=404)

            resolved_variables = {
                k: str(v) for k, v in (task.request_snapshot.get("resolved_variables") or {}).items()
            }
            user_selection_payloads = task.request_snapshot.get("user_chapter_selections") or []
            selections = [UserChapterSelection(**item) for item in user_selection_payloads]
            template_rows = self._load_suggested_template_chapters(suggestion)
            conflict_ids, risk_flags = self.conflict_detector.detect(
                template_chapters=template_rows,
                rejection_clauses=context.rejection_clauses or [],
            )
            product_category_ids = ConditionalChapterEvaluator.resolve_product_category_ids(
                request_product_category_ids=task.request_snapshot.get("product_category_ids"),
                suggestion=suggestion,
            )
            chapter_evaluation = self.chapter_evaluator.evaluate(
                self.db,
                kb_id=task.kb_id,
                template_chapters=template_rows,
                product_category_ids=product_category_ids,
                customer_type=suggestion.customer_type if suggestion else None,
                requirement_context=context,
                user_chapter_selections=selections,
                conflict_template_ids=conflict_ids,
                conflict_risk_flags=risk_flags,
            )
            resolved = self.resolver.resolve(
                requirement_context=context,
                suggestion=suggestion or self._empty_suggestion(task),
                target_outline_node=task.target_outline_node,
                user_chapter_selections=selections,
                resolved_variables=resolved_variables,
                conflict_template_ids=conflict_ids,
            )
            resolved.conflict_pre_flags = risk_flags
            resolved.suggested_chapter_enables = chapter_evaluation.suggested_chapter_enables
            resolved.user_chapter_selections = [
                item.model_dump(mode="json") for item in selections
            ]

            manual_asset_compliance = task.request_snapshot.get("manual_asset_compliance") or []
            resolved, missing_material_hints = self.compliance_checker.apply(
                resolved=resolved,
                manual_asset_compliance=manual_asset_compliance,
            )

            system_prompt, user_prompt = self.prompt_builder.build(
                resolved,
                resolved_variables,
                target_outline_node=task.target_outline_node,
            )
            llm_response = chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=4096,
            )
            if llm_response is None:
                raise GenerationServiceError("LLM generation failed", code="GENERATION_FAILED")

            llm_payload = self._parse_llm_json(llm_response.content)
            paragraphs_input = llm_payload.get("paragraphs")
            if not isinstance(paragraphs_input, list):
                raise GenerationServiceError("LLM payload paragraphs invalid", code="PARSE_FAILED")

            bound_paragraphs = self.citation_binder.bind(
                llm_paragraphs=paragraphs_input,
                catalog=resolved.source_catalog,
                resolved_variables=resolved_variables,
            )
            conflict_hints = self._build_post_conflict_hints(bound_paragraphs, conflict_ids)
            retrieval_trace_summary = build_retrieval_trace_summary(self.db, suggestion)
            version_tag = task.request_snapshot.get("version_tag") or "v1"
            snapshot = self.snapshot_writer.write(
                task=task,
                requirement_context=context,
                suggestion=suggestion,
                resolved_context=resolved,
                variable_inputs=resolved_variables,
                retrieval_trace_summary=retrieval_trace_summary,
                conflict_hints=conflict_hints,
                missing_material_hints=missing_material_hints,
                paragraphs=bound_paragraphs,
                result_version=version_tag,
            )

            draft = ChapterDraft(
                kb_id=task.kb_id,
                task_id=task.task_id,
                snapshot_id=snapshot.snapshot_id,
                requirement_context_id=task.requirement_context_id,
                suggestion_id=task.suggestion_id,
                target_outline_node=task.target_outline_node,
                paragraphs=bound_paragraphs,
                conflict_hints=conflict_hints,
                missing_material_hints=missing_material_hints,
                version_tag=version_tag,
            )
            self.db.add(draft)
            self.db.flush()

            task.draft_id = draft.draft_id
            task.request_snapshot = {
                **task.request_snapshot,
                "snapshot_id": str(snapshot.snapshot_id),
            }
            task.status = GenerationTaskStatus.completed
            task.completed_at = datetime.now(timezone.utc)
            self.db.flush()
        except GenerationServiceError as exc:
            self._mark_failed(task, code=exc.code, message=str(exc))
        except Exception as exc:  # pragma: no cover - safety net
            self._mark_failed(task, code="GENERATION_FAILED", message=str(exc))

    def _mark_failed(self, task: GenerationTask, *, code: str, message: str) -> None:
        task.status = GenerationTaskStatus.failed
        task.error_code = code
        task.error_message = message[:1000]
        task.completed_at = datetime.now(timezone.utc)
        self.db.flush()

    def _load_suggested_template_chapters(
        self, suggestion: ModuleAssemblySuggestion | None
    ) -> list[TemplateChapter]:
        if suggestion is None:
            return []
        template_chapter_ids: list[UUID] = []
        for item in suggestion.suggested_template_chapter_ids or []:
            raw = str(item).strip()
            if not raw:
                continue
            try:
                template_chapter_ids.append(UUID(raw))
            except ValueError:
                continue
        if not template_chapter_ids:
            return []
        rows = (
            self.db.query(TemplateChapter)
            .filter(
                TemplateChapter.kb_id == suggestion.kb_id,
                TemplateChapter.template_chapter_id.in_(template_chapter_ids),
            )
            .all()
        )
        return rows

    @staticmethod
    def _parse_llm_json(raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise GenerationServiceError("LLM payload JSON parse failed", code="PARSE_FAILED") from exc

    @staticmethod
    def _build_post_conflict_hints(paragraphs: list[dict], conflict_ids: set[str]) -> list[dict]:
        if not conflict_ids:
            return []
        hints: list[dict] = []
        for paragraph in paragraphs:
            for citation in paragraph.get("citations") or []:
                if citation.get("source_type") != "template_chapter":
                    continue
                template_id = str(citation.get("source_id"))
                if template_id not in conflict_ids:
                    continue
                hints.append(
                    {
                        "type": "template_vs_rejection",
                        "template_chapter_id": template_id,
                        "message": "引用命中冲突模板章节，请人工复核",
                        "severity": "high",
                    }
                )
        dedup: dict[str, dict] = {}
        for item in hints:
            dedup[item["template_chapter_id"]] = item
        return list(dedup.values())

    @staticmethod
    def _empty_suggestion(task: GenerationTask) -> ModuleAssemblySuggestion:
        return ModuleAssemblySuggestion(
            kb_id=task.kb_id,
            trace_id=task.trace_id or UUID("00000000-0000-0000-0000-000000000000"),
            target_outline_node=task.target_outline_node,
            suggested_template_chapter_ids=[],
            match_score=0.0,
            coverage_rate=0.0,
            score_detail={},
        )
