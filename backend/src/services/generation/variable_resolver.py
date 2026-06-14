from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus
from src.models.manual_asset import ManualAsset, ManualAssetStatus
from src.models.module_assembly_suggestion import (
    ModuleAssemblySuggestion,
    ModuleAssemblySuggestionStatus,
)
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.models.template_variable import TemplateVariable, TemplateVariableStatus
from src.models.wiki import Wiki, WikiStatus
from src.schemas.generation import UserChapterSelection
from src.services.generation.tender_requirement_service import TenderRequirementService
from src.services.retrieval.module_suggestion.module_suggestion_service import ModuleSuggestionService


class MissingRequiredVariablesError(Exception):
    def __init__(self, *, missing_keys: list[str]):
        self.missing_keys = sorted(missing_keys)
        super().__init__(f"required variables missing: {', '.join(self.missing_keys)}")


class GenerationPreflightError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: dict | None = None,
    ):
        self.code = code
        self.details = details
        super().__init__(message)


class VariableResolver:
    def validate_and_resolve(
        self,
        *,
        variables: list[TemplateVariable],
        values: dict[str, str],
    ) -> dict[str, str]:
        by_key = self._dedupe_variables(variables)
        resolved: dict[str, str] = {}
        missing_keys: list[str] = []

        for key, variable in by_key.items():
            user_value = values.get(key)
            if user_value is not None and str(user_value).strip():
                resolved[key] = str(user_value).strip()
                continue

            default_value = variable.default_value
            if default_value is not None and str(default_value).strip():
                resolved[key] = str(default_value).strip()
                continue

            if variable.required:
                missing_keys.append(key)
            else:
                resolved[key] = ""

        if missing_keys:
            raise MissingRequiredVariablesError(missing_keys=missing_keys)
        return resolved

    def replace_placeholders(self, text: str, resolved: dict[str, str]) -> str:
        result = text
        for key, value in resolved.items():
            result = result.replace(f"{{{{{key}}}}}", value)
            pattern = re.compile(r"\{\{\s*" + re.escape(key) + r"\s*\}\}")
            result = pattern.sub(value, result)
        return result

    def collect_for_template_chapters(
        self,
        db: Session,
        kb_id: UUID,
        template_chapter_ids: list[UUID],
    ) -> list[TemplateVariable]:
        if not template_chapter_ids:
            return []

        return (
            db.query(TemplateVariable)
            .filter(
                TemplateVariable.kb_id == kb_id,
                TemplateVariable.template_chapter_id.in_(template_chapter_ids),
                TemplateVariable.status == TemplateVariableStatus.active,
            )
            .order_by(TemplateVariable.variable_key.asc())
            .all()
        )

    @staticmethod
    def _dedupe_variables(variables: list[TemplateVariable]) -> dict[str, TemplateVariable]:
        by_key: dict[str, TemplateVariable] = {}
        for variable in variables:
            existing = by_key.get(variable.variable_key)
            if existing is None:
                by_key[variable.variable_key] = variable
            elif variable.required and not existing.required:
                by_key[variable.variable_key] = variable
        return by_key


def validate_generation_variables(
    db: Session,
    *,
    kb_id: UUID,
    suggestion_id: UUID,
    variable_values: dict[str, str],
    confirm_adoption: bool = False,
) -> dict[str, str]:
    suggestion = ModuleSuggestionService(db).get_suggestion(
        kb_id=kb_id,
        suggestion_id=suggestion_id,
    )
    if suggestion is None:
        raise GenerationPreflightError("module suggestion not found", code="NOT_FOUND")

    if suggestion.status != ModuleAssemblySuggestionStatus.adopted:
        if not (
            confirm_adoption
            and suggestion.status == ModuleAssemblySuggestionStatus.draft
        ):
            raise GenerationPreflightError(
                "module suggestion must be adopted before generation",
                code="SUGGESTION_NOT_ADOPTED",
            )

    chapter_ids = _parse_template_chapter_ids(suggestion)
    variables = VariableResolver().collect_for_template_chapters(db, kb_id, chapter_ids)
    try:
        return VariableResolver().validate_and_resolve(
            variables=variables,
            values=variable_values,
        )
    except MissingRequiredVariablesError as exc:
        raise GenerationPreflightError(
            "required variables missing",
            code="MISSING_REQUIRED_VARIABLES",
            details={"missing_keys": exc.missing_keys},
        ) from exc


def validate_published_assets(
    db: Session,
    *,
    kb_id: UUID,
    suggestion: ModuleAssemblySuggestion,
    user_chapter_selections: list[UserChapterSelection] | None = None,
) -> None:
    unpublished: list[dict[str, str]] = []

    template_chapter_ids = set(_parse_template_chapter_ids(suggestion))
    for selection in user_chapter_selections or []:
        template_chapter_ids.add(selection.template_chapter_id)

    if template_chapter_ids:
        rows = (
            db.query(TemplateChapter)
            .filter(
                TemplateChapter.kb_id == kb_id,
                TemplateChapter.template_chapter_id.in_(template_chapter_ids),
            )
            .all()
        )
        found = {row.template_chapter_id: row for row in rows}
        for chapter_id in template_chapter_ids:
            row = found.get(chapter_id)
            if row is None or row.status != TemplateChapterStatus.published:
                unpublished.append({"type": "template_chapter", "id": str(chapter_id)})

    ku_ids = [_parse_uuid(raw_id) for raw_id in suggestion.suggested_ku_ids or []]
    if ku_ids:
        rows = (
            db.query(KnowledgeUnit)
            .filter(KnowledgeUnit.kb_id == kb_id, KnowledgeUnit.ku_id.in_(ku_ids))
            .all()
        )
        found = {row.ku_id: row for row in rows}
        for ku_id in ku_ids:
            row = found.get(ku_id)
            if row is None or row.status != KnowledgeUnitStatus.published:
                unpublished.append({"type": "ku", "id": str(ku_id)})

    wiki_ids = [_parse_uuid(raw_id) for raw_id in suggestion.suggested_wiki_ids or []]
    if wiki_ids:
        rows = db.query(Wiki).filter(Wiki.kb_id == kb_id, Wiki.wiki_id.in_(wiki_ids)).all()
        found = {row.wiki_id: row for row in rows}
        for wiki_id in wiki_ids:
            row = found.get(wiki_id)
            if row is None or row.status != WikiStatus.published:
                unpublished.append({"type": "wiki", "id": str(wiki_id)})

    manual_asset_ids = [
        _parse_uuid(raw_id) for raw_id in suggestion.suggested_manual_asset_ids or []
    ]
    if manual_asset_ids:
        rows = (
            db.query(ManualAsset)
            .filter(
                ManualAsset.kb_id == kb_id,
                ManualAsset.manual_asset_id.in_(manual_asset_ids),
            )
            .all()
        )
        found = {row.manual_asset_id: row for row in rows}
        for manual_asset_id in manual_asset_ids:
            row = found.get(manual_asset_id)
            if row is None or row.status != ManualAssetStatus.published:
                unpublished.append({"type": "manual_asset", "id": str(manual_asset_id)})

    if unpublished:
        raise GenerationPreflightError(
            "referenced assets are not published",
            code="ASSET_NOT_PUBLISHED",
            details={"assets": unpublished},
        )


def epic6_draft_preflight(
    db: Session,
    *,
    kb_id: UUID,
    requirement_context_id: UUID,
    suggestion_id: UUID,
    variable_values: dict[str, str],
    confirm_adoption: bool = False,
    user_chapter_selections: list[UserChapterSelection] | None = None,
) -> dict[str, str]:
    context = TenderRequirementService(db).get(
        kb_id=kb_id,
        requirement_context_id=requirement_context_id,
    )
    if context is None:
        raise GenerationPreflightError(
            "tender requirement context not found",
            code="NOT_FOUND",
        )

    suggestion = ModuleSuggestionService(db).get_suggestion(
        kb_id=kb_id,
        suggestion_id=suggestion_id,
    )
    if suggestion is None:
        raise GenerationPreflightError("module suggestion not found", code="NOT_FOUND")

    if (
        suggestion.requirement_context_id is not None
        and suggestion.requirement_context_id != requirement_context_id
    ):
        raise GenerationPreflightError(
            "requirement context does not match suggestion",
            code="NOT_FOUND",
        )

    validate_published_assets(
        db,
        kb_id=kb_id,
        suggestion=suggestion,
        user_chapter_selections=user_chapter_selections,
    )

    return validate_generation_variables(
        db,
        kb_id=kb_id,
        suggestion_id=suggestion_id,
        variable_values=variable_values,
        confirm_adoption=confirm_adoption,
    )


def _parse_template_chapter_ids(suggestion: ModuleAssemblySuggestion) -> list[UUID]:
    chapter_ids: list[UUID] = []
    for raw_id in suggestion.suggested_template_chapter_ids or []:
        chapter_ids.append(_parse_uuid(raw_id))
    return chapter_ids


def _parse_uuid(raw_id: object) -> UUID:
    return UUID(str(raw_id))
