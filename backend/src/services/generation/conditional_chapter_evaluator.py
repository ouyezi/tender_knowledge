from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.module_assembly_suggestion import ModuleAssemblySuggestion
from src.models.template_chapter import TemplateChapter
from src.models.template_rule import TemplateRule, TemplateRuleAction, TemplateRuleStatus, TemplateRuleType
from src.models.tender_requirement_context import TenderRequirementContext
from src.schemas.generation import UserChapterSelection


@dataclass
class ConditionalChapterEvaluationResult:
    suggested_chapter_enables: list[dict[str, Any]] = field(default_factory=list)


class ConditionalChapterEvaluator:
    _EVALUATED_RULE_TYPES = {TemplateRuleType.product_match, TemplateRuleType.conditional}

    def evaluate(
        self,
        db: Session,
        *,
        kb_id: UUID,
        template_chapters: list[TemplateChapter],
        product_category_ids: list[Any],
        customer_type: str | None,
        requirement_context: TenderRequirementContext,
        user_chapter_selections: list[UserChapterSelection],
        conflict_template_ids: set[str] | None = None,
        conflict_risk_flags: list[dict[str, Any]] | None = None,
    ) -> ConditionalChapterEvaluationResult:
        if not template_chapters:
            return ConditionalChapterEvaluationResult()

        chapter_ids = [chapter.template_chapter_id for chapter in template_chapters]
        rules = (
            db.query(TemplateRule)
            .filter(
                TemplateRule.kb_id == kb_id,
                TemplateRule.template_chapter_id.in_(chapter_ids),
                TemplateRule.rule_type.in_(self._EVALUATED_RULE_TYPES),
                TemplateRule.status == TemplateRuleStatus.active,
            )
            .all()
        )
        if not rules:
            return ConditionalChapterEvaluationResult()

        normalized_categories = {str(item).strip() for item in product_category_ids if str(item).strip()}
        tender_text = self._build_tender_text(requirement_context)
        user_selection_by_chapter = {
            str(item.template_chapter_id): item for item in user_chapter_selections
        }
        conflict_template_ids = conflict_template_ids or set()
        conflict_risk_by_chapter = self._index_conflict_risk_flags(conflict_risk_flags or [])
        chapter_titles = {
            str(chapter.template_chapter_id): (chapter.title or "").strip()
            for chapter in template_chapters
        }

        suggestions: list[dict[str, Any]] = []
        seen_chapters: set[str] = set()
        for rule in rules:
            chapter_id = str(rule.template_chapter_id)
            if chapter_id in seen_chapters:
                continue
            if not self._rule_matches(
                rule=rule,
                product_category_ids=normalized_categories,
                customer_type=customer_type,
                tender_text=tender_text,
                user_selection_by_chapter=user_selection_by_chapter,
            ):
                continue

            enabled = rule.action == TemplateRuleAction.enable
            reason = (rule.message or "").strip() or self._default_reason(rule)
            risk_flags = list(conflict_risk_by_chapter.get(chapter_id, []))
            if chapter_id in conflict_template_ids and not risk_flags:
                risk_flags.append(
                    {
                        "template_chapter_id": chapter_id,
                        "risk_type": "tender_template_conflict",
                        "reason": "条件章节与招标废标项存在冲突，不建议默认采用",
                    }
                )

            suggestions.append(
                {
                    "template_chapter_id": chapter_id,
                    "template_chapter_title": chapter_titles.get(chapter_id),
                    "enabled": enabled,
                    "reason": reason,
                    "rule_id": str(rule.rule_id),
                    "rule_type": rule.rule_type.value,
                    "risk_flags": risk_flags,
                }
            )
            seen_chapters.add(chapter_id)

        return ConditionalChapterEvaluationResult(suggested_chapter_enables=suggestions)

    @staticmethod
    def _index_conflict_risk_flags(
        risk_flags: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        indexed: dict[str, list[dict[str, Any]]] = {}
        for item in risk_flags:
            chapter_id = str(item.get("template_chapter_id") or "").strip()
            if not chapter_id:
                continue
            indexed.setdefault(chapter_id, []).append(item)
        return indexed

    @staticmethod
    def _build_tender_text(requirement_context: TenderRequirementContext) -> str:
        parts: list[str] = []
        for collection in (
            requirement_context.rejection_clauses,
            requirement_context.score_points,
            requirement_context.response_clauses,
            requirement_context.format_requirements,
            requirement_context.qualification_requirements,
        ):
            for item in collection or []:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("value") or item))
                else:
                    parts.append(str(item))
        return "\n".join(part for part in parts if part.strip())

    def _rule_matches(
        self,
        *,
        rule: TemplateRule,
        product_category_ids: set[str],
        customer_type: str | None,
        tender_text: str,
        user_selection_by_chapter: dict[str, UserChapterSelection],
    ) -> bool:
        condition = rule.condition or {}
        if rule.rule_type == TemplateRuleType.product_match:
            return self._match_product_category(condition, product_category_ids)

        field_name = str(condition.get("field") or "").strip()
        if field_name == "product_category":
            return self._match_product_category(condition, product_category_ids)
        if field_name == "customer_type":
            return self._match_scalar(condition, customer_type)
        if field_name == "tender_keyword":
            return self._match_tender_keyword(condition, tender_text)
        if field_name == "user_chapter_selection":
            chapter_id = str(rule.template_chapter_id)
            selection = user_selection_by_chapter.get(chapter_id)
            if selection is None:
                return False
            expected = condition.get("value")
            if expected is None:
                return selection.enabled
            if isinstance(expected, bool):
                return selection.enabled is expected
            return str(selection.enabled).lower() == str(expected).lower()
        return False

    @staticmethod
    def _match_product_category(condition: dict[str, Any], product_category_ids: set[str]) -> bool:
        operator = str(condition.get("operator") or "in").strip()
        raw_value = condition.get("value")
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        normalized_values = {str(item).strip() for item in values if str(item).strip()}
        if not normalized_values:
            return False
        if operator == "eq":
            return any(value in product_category_ids for value in normalized_values)
        return bool(product_category_ids & normalized_values)

    @staticmethod
    def _match_scalar(condition: dict[str, Any], actual: str | None) -> bool:
        if actual is None:
            return False
        operator = str(condition.get("operator") or "in").strip()
        raw_value = condition.get("value")
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        normalized_values = {str(item).strip() for item in values if str(item).strip()}
        if operator == "eq":
            return actual in normalized_values
        return actual in normalized_values

    @staticmethod
    def _match_tender_keyword(condition: dict[str, Any], tender_text: str) -> bool:
        raw_value = condition.get("value")
        keywords = raw_value if isinstance(raw_value, list) else [raw_value]
        normalized_keywords = [str(item).strip() for item in keywords if str(item).strip()]
        if not normalized_keywords or not tender_text.strip():
            return False
        operator = str(condition.get("operator") or "contains").strip()
        if operator == "eq":
            return tender_text.strip() in normalized_keywords
        return any(keyword in tender_text for keyword in normalized_keywords)

    @staticmethod
    def _default_reason(rule: TemplateRule) -> str:
        if rule.rule_type == TemplateRuleType.product_match:
            return "产品分类匹配，建议启用条件章节"
        return "条件规则匹配，建议启用条件章节"

    @staticmethod
    def resolve_product_category_ids(
        *,
        request_product_category_ids: list[Any] | None,
        suggestion: ModuleAssemblySuggestion | None,
    ) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for source in (request_product_category_ids or [], (suggestion.product_category_ids if suggestion else []) or []):
            for item in source:
                normalized = str(item).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                merged.append(normalized)
        return merged
