from __future__ import annotations

# G4 audit checklist (Constitution G4 / FR-010 Generation Snapshot):
# - requirement_context_id + requirement_context_snapshot (招标约束引用)
# - suggestion_id + suggestion_snapshot (模块建议引用)
# - target_outline_node (目标 outline 节点)
# - used_ku_ids / used_wiki_ids / used_template_chapter_ids / used_manual_asset_ids
# - variable_inputs (变量输入与值)
# - retrieval_trace_summary (检索 trace 摘要)
# - prompt_version (生成 prompt 版本)
# - result_version (生成结果版本)
# - conflict_hints / missing_material_hints (冲突与缺失素材提示)
# - input_priority_layers (多源输入优先级层摘要)

from sqlalchemy.orm import Session

from src.models.generation_snapshot import GenerationSnapshot
from src.models.generation_task import GenerationTask
from src.models.module_assembly_suggestion import ModuleAssemblySuggestion
from src.models.retrieval_trace import RetrievalTrace
from src.models.tender_requirement_context import TenderRequirementContext
from src.schemas.generation import ResolvedGenerationContext
from src.services.generation.prompt_seed import GENERATION_PROMPT_VERSION


def build_retrieval_trace_summary(
    db: Session,
    suggestion: ModuleAssemblySuggestion | None,
) -> dict | None:
    if suggestion is None or suggestion.trace_id is None:
        return None
    trace = db.get(RetrievalTrace, suggestion.trace_id)
    if trace is None:
        return {"trace_id": str(suggestion.trace_id)}
    return {
        "trace_id": str(trace.trace_id),
        "intent": trace.intent.value,
        "status": trace.status.value,
    }


class SnapshotWriter:
    def __init__(self, db: Session) -> None:
        self.db = db

    def write(
        self,
        *,
        task: GenerationTask,
        requirement_context: TenderRequirementContext,
        suggestion: ModuleAssemblySuggestion | None,
        resolved_context: ResolvedGenerationContext,
        variable_inputs: dict[str, str],
        retrieval_trace_summary: dict | None,
        conflict_hints: list[dict],
        missing_material_hints: list[dict],
        paragraphs: list[dict],
        result_version: str = "v1",
    ) -> GenerationSnapshot:
        used_ku_ids: set[str] = set()
        used_wiki_ids: set[str] = set()
        used_template_chapter_ids: set[str] = set()
        used_manual_asset_ids: set[str] = set()

        for paragraph in paragraphs:
            for citation in paragraph.get("citations", []):
                source_type = str(citation.get("source_type"))
                source_id = str(citation.get("source_id"))
                if source_type == "ku":
                    used_ku_ids.add(source_id)
                elif source_type == "wiki":
                    used_wiki_ids.add(source_id)
                elif source_type == "template_chapter":
                    used_template_chapter_ids.add(source_id)
                elif source_type == "manual_asset":
                    used_manual_asset_ids.add(source_id)

        requirement_context_snapshot = {
            "requirement_context_id": str(requirement_context.requirement_context_id),
            "title": requirement_context.title,
            "outline_structure": requirement_context.outline_structure,
            "outline_nodes": requirement_context.outline_nodes,
            "score_points": requirement_context.score_points,
            "rejection_clauses": requirement_context.rejection_clauses,
            "format_requirements": requirement_context.format_requirements,
            "qualification_requirements": requirement_context.qualification_requirements,
            "response_clauses": requirement_context.response_clauses,
            "source_note": requirement_context.source_note,
        }
        suggestion_snapshot = None
        if suggestion is not None:
            suggestion_snapshot = {
                "suggestion_id": str(suggestion.suggestion_id),
                "trace_id": str(suggestion.trace_id),
                "target_outline_node": suggestion.target_outline_node,
                "suggested_template_chapter_ids": suggestion.suggested_template_chapter_ids,
                "suggested_ku_ids": suggestion.suggested_ku_ids,
                "suggested_wiki_ids": suggestion.suggested_wiki_ids,
                "suggested_manual_asset_ids": suggestion.suggested_manual_asset_ids,
                "knowledge_pack_snapshot": suggestion.knowledge_pack_snapshot,
                "risk_flags": suggestion.risk_flags,
            }

        resolved_trace_summary = retrieval_trace_summary
        if resolved_trace_summary is None:
            resolved_trace_summary = build_retrieval_trace_summary(self.db, suggestion)

        snapshot = GenerationSnapshot(
            kb_id=task.kb_id,
            task_id=task.task_id,
            requirement_context_id=task.requirement_context_id,
            requirement_context_snapshot=requirement_context_snapshot,
            suggestion_id=task.suggestion_id,
            suggestion_snapshot=suggestion_snapshot,
            target_outline_node=task.target_outline_node,
            used_ku_ids=sorted(used_ku_ids),
            used_wiki_ids=sorted(used_wiki_ids),
            used_template_chapter_ids=sorted(used_template_chapter_ids),
            used_manual_asset_ids=sorted(used_manual_asset_ids),
            variable_inputs=variable_inputs,
            retrieval_trace_summary=resolved_trace_summary,
            prompt_version=GENERATION_PROMPT_VERSION,
            result_version=result_version,
            conflict_hints=conflict_hints,
            missing_material_hints=missing_material_hints,
            input_priority_layers={
                **{k: len(v) for k, v in resolved_context.layers.items()},
                "user_chapter_selections": resolved_context.user_chapter_selections,
                "suggested_chapter_enables": resolved_context.suggested_chapter_enables,
            },
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot
