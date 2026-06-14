from __future__ import annotations

from dataclasses import dataclass

from src.models.module_assembly_suggestion import ModuleAssemblySuggestion
from src.models.tender_requirement_context import TenderRequirementContext
from src.schemas.generation import ResolvedGenerationContext, SourceCatalogEntry, UserChapterSelection


@dataclass
class _SourceBuilder:
    counter: int = 1

    def next_ref_id(self) -> str:
        ref_id = f"SRC-{self.counter:03d}"
        self.counter += 1
        return ref_id


class InputPriorityResolver:
    def resolve(
        self,
        *,
        requirement_context: TenderRequirementContext,
        suggestion: ModuleAssemblySuggestion,
        target_outline_node: dict,
        user_chapter_selections: list[UserChapterSelection],
        resolved_variables: dict[str, str],
        conflict_template_ids: set[str] | None = None,
    ) -> ResolvedGenerationContext:
        source_builder = _SourceBuilder()
        catalog: list[SourceCatalogEntry] = []
        layers: dict[str, list[str]] = {
            "rejection_clauses": [],
            "score_points": [],
            "outline_structure": [],
            "user_selections": [],
            "knowledge_pack": [],
            "template_hints": [],
        }
        conflict_template_ids = conflict_template_ids or set()

        for idx, clause in enumerate(requirement_context.rejection_clauses or []):
            text = str(clause)
            ref_id = f"TREQ-RC-{idx}"
            catalog.append(
                SourceCatalogEntry(
                    ref_id=ref_id,
                    type="tender_requirement",
                    object_id=f"rejection_clause:{idx}",
                    title=f"废标项 {idx}",
                    excerpt=text,
                )
            )
            layers["rejection_clauses"].append(f"[{ref_id}] {text}")

        for idx, point in enumerate(requirement_context.score_points or []):
            if isinstance(point, dict):
                text = str(point.get("text") or point.get("value") or point)
            else:
                text = str(point)
            ref_id = f"TREQ-SP-{idx}"
            catalog.append(
                SourceCatalogEntry(
                    ref_id=ref_id,
                    type="tender_requirement",
                    object_id=f"score_point:{idx}",
                    title=f"评分点 {idx}",
                    excerpt=text,
                )
            )
            layers["score_points"].append(f"[{ref_id}] {text}")

        layers["outline_structure"].append(
            f"target_outline_node={target_outline_node}; outline_nodes={requirement_context.outline_nodes or []}"
        )

        for item in user_chapter_selections:
            if not item.enabled:
                continue
            layers["user_selections"].append(
                f"template_chapter_id={item.template_chapter_id}, source={item.source}"
            )

        seen_keys: set[tuple[str, str | None]] = set()
        for item in suggestion.knowledge_pack_snapshot or []:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("type") or item.get("object_type") or "").strip()
            object_id = str(item.get("object_id") or item.get("id") or "").strip() or None
            if source_type not in {"ku", "wiki", "manual_asset", "template_chapter"}:
                continue
            dedupe_key = (source_type, object_id)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            title = str(item.get("title") or f"{source_type} {object_id or ''}").strip()
            excerpt = str(
                item.get("excerpt") or item.get("summary") or item.get("content") or title
            ).strip()
            ref_id = source_builder.next_ref_id()
            catalog.append(
                SourceCatalogEntry(
                    ref_id=ref_id,
                    type=source_type,
                    object_id=object_id,
                    title=title,
                    excerpt=excerpt,
                )
            )
            layers["knowledge_pack"].append(f"[{ref_id}] {title}: {excerpt}")

        for raw_template_id in suggestion.suggested_template_chapter_ids or []:
            template_id = str(raw_template_id)
            if template_id in conflict_template_ids:
                continue
            dedupe_key = ("template_chapter", template_id)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            ref_id = source_builder.next_ref_id()
            title = f"模板章节 {template_id}"
            catalog.append(
                SourceCatalogEntry(
                    ref_id=ref_id,
                    type="template_chapter",
                    object_id=template_id,
                    title=title,
                    excerpt=title,
                )
            )
            layers["template_hints"].append(f"[{ref_id}] {title}")

        for key, value in sorted(resolved_variables.items()):
            ref_id = f"VAR-{key}"
            catalog.append(
                SourceCatalogEntry(
                    ref_id=ref_id,
                    type="variable",
                    object_id=key,
                    title=f"变量 {key}",
                    excerpt=value,
                )
            )

        return ResolvedGenerationContext(
            layers=layers,
            source_catalog=catalog,
            conflict_pre_flags=[],
        )
