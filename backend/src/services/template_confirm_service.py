from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.candidate_knowledge_stub import (
    CandidateKnowledgeStub,
    CandidateKnowledgeType,
)
from src.models.template import Template, TemplateType
from src.models.template_audit_log import TemplateAuditAction, TemplateAuditLog
from src.models.template_chapter import TemplateChapter
from src.models.template_library import TemplateLibrary, TemplateLibraryType
from src.models.template_material import TemplateMaterial, TemplateMaterialType
from src.models.template_parse_suggestion import TemplateParseSuggestion
from src.models.template_parse_task import TemplateParseTask, TemplateParseTaskStatus


class TemplateConfirmServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


@dataclass
class ConfirmParseResult:
    parse_task_id: UUID
    template_id: UUID
    template_library_id: UUID | None
    status: str
    structure_locked_at: datetime
    candidate_stubs_created: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_uuid(value: Any, *, field_name: str) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise TemplateConfirmServiceError(
            f"Invalid UUID for {field_name}",
            code="INVALID_INPUT",
            status_code=422,
        ) from exc


def _as_uuid_list(values: Any, *, field_name: str) -> list[UUID]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise TemplateConfirmServiceError(
            f"{field_name} must be a list",
            code="INVALID_INPUT",
            status_code=422,
        )
    return [uuid for item in values if (uuid := _as_uuid(item, field_name=field_name)) is not None]


def _material_type(value: Any) -> TemplateMaterialType:
    try:
        return TemplateMaterialType(str(value))
    except ValueError as exc:
        raise TemplateConfirmServiceError(
            f"Unsupported material_type: {value}",
            code="INVALID_INPUT",
            status_code=422,
        ) from exc


def _candidate_type(value: Any) -> CandidateKnowledgeType:
    try:
        return CandidateKnowledgeType(str(value))
    except ValueError as exc:
        raise TemplateConfirmServiceError(
            f"Unsupported candidate_type: {value}",
            code="INVALID_INPUT",
            status_code=422,
        ) from exc


def _template_type(value: Any) -> TemplateType:
    try:
        return TemplateType(str(value))
    except ValueError as exc:
        raise TemplateConfirmServiceError(
            f"Unsupported template_type: {value}",
            code="INVALID_INPUT",
            status_code=422,
        ) from exc


def _template_library_type(value: Any) -> TemplateLibraryType:
    try:
        return TemplateLibraryType(str(value))
    except ValueError as exc:
        raise TemplateConfirmServiceError(
            f"Unsupported library_type: {value}",
            code="INVALID_INPUT",
            status_code=422,
        ) from exc


def _prepare_library(
    db: Session,
    *,
    kb_id: UUID,
    template: Template,
    body: dict[str, Any],
    operator_id: str,
) -> UUID | None:
    library_id = _as_uuid(body.get("template_library_id"), field_name="template_library_id")
    create_library = body.get("create_library")
    if library_id and create_library:
        raise TemplateConfirmServiceError(
            "template_library_id and create_library cannot be used together",
            code="INVALID_INPUT",
            status_code=422,
        )

    if create_library:
        library_name = str(create_library.get("library_name", "")).strip()
        library_type_raw = create_library.get("library_type")
        if not library_name:
            raise TemplateConfirmServiceError(
                "library_name is required when create_library is provided",
                code="INVALID_INPUT",
                status_code=422,
            )
        library_type = _template_library_type(library_type_raw)
        library = TemplateLibrary(
            kb_id=kb_id,
            library_name=library_name,
            library_type=library_type,
            source_import_id=template.source_import_id,
            product_category_ids=_as_uuid_list(
                body.get("product_category_ids"),
                field_name="product_category_ids",
            ),
            created_by=operator_id,
        )
        db.add(library)
        db.flush()
        return library.template_library_id

    if library_id is None:
        return None

    library = (
        db.query(TemplateLibrary)
        .filter(
            TemplateLibrary.kb_id == kb_id,
            TemplateLibrary.template_library_id == library_id,
        )
        .one_or_none()
    )
    if library is None:
        raise TemplateConfirmServiceError(
            "Template library not found",
            code="NOT_FOUND",
            status_code=404,
        )
    return library_id


def _replace_chapters(
    db: Session,
    *,
    template: Template,
    chapters: list[dict[str, Any]],
) -> dict[str, TemplateChapter]:
    db.query(TemplateChapter).filter(TemplateChapter.template_id == template.template_id).delete(
        synchronize_session=False
    )

    created_by_temp: dict[str, TemplateChapter] = {}
    parent_by_temp: dict[str, str | None] = {}

    for chapter in chapters:
        temp_id = str(chapter.get("temp_id", "")).strip()
        if not temp_id:
            raise TemplateConfirmServiceError(
                "Each chapter must include temp_id",
                code="INVALID_INPUT",
                status_code=422,
            )
        row = TemplateChapter(
            kb_id=template.kb_id,
            template_id=template.template_id,
            title=str(chapter.get("title", "")).strip() or temp_id,
            level=int(chapter.get("level", 1) or 1),
            sort_order=int(chapter.get("sort_order", 0) or 0),
            chapter_taxonomy_id=_as_uuid(
                chapter.get("chapter_taxonomy_id"),
                field_name="chapter_taxonomy_id",
            ),
            product_category_ids=_as_uuid_list(
                chapter.get("product_category_ids"),
                field_name="chapter.product_category_ids",
            ),
            required=bool(chapter.get("required", False)),
            is_fixed_section=bool(chapter.get("is_fixed_section", False)),
            ignored=bool(chapter.get("ignored", False)),
            parse_source_ref=temp_id,
        )
        db.add(row)
        db.flush()
        created_by_temp[temp_id] = row
        parent_by_temp[temp_id] = (
            str(chapter.get("parent_temp_id")) if chapter.get("parent_temp_id") else None
        )

    for temp_id, row in created_by_temp.items():
        parent_temp = parent_by_temp.get(temp_id)
        if not parent_temp:
            continue
        parent = created_by_temp.get(parent_temp)
        if parent is None:
            raise TemplateConfirmServiceError(
                f"parent_temp_id not found: {parent_temp}",
                code="INVALID_INPUT",
                status_code=422,
            )
        row.parent_id = parent.template_chapter_id
    return created_by_temp


def confirm_parse_task(
    db: Session,
    *,
    kb_id: UUID,
    parse_task_id: UUID,
    body: dict[str, Any],
    operator_id: str,
    trace_id: UUID,
) -> ConfirmParseResult:
    task = (
        db.query(TemplateParseTask)
        .filter(TemplateParseTask.kb_id == kb_id, TemplateParseTask.parse_task_id == parse_task_id)
        .one_or_none()
    )
    if task is None:
        raise TemplateConfirmServiceError("Parse task not found", code="NOT_FOUND", status_code=404)
    if task.status != TemplateParseTaskStatus.parse_ready:
        raise TemplateConfirmServiceError(
            "Only parse_ready tasks can be confirmed",
            code="INVALID_STATE",
            status_code=422,
        )
    if task.template_id is None:
        raise TemplateConfirmServiceError(
            "Parse task template is missing",
            code="INVALID_STATE",
            status_code=422,
        )

    template = (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_id == task.template_id)
        .one_or_none()
    )
    if template is None:
        raise TemplateConfirmServiceError("Template not found", code="NOT_FOUND", status_code=404)

    library_id = _prepare_library(
        db,
        kb_id=kb_id,
        template=template,
        body=body,
        operator_id=operator_id,
    )

    template.template_library_id = library_id
    template.template_name = str(body.get("template_name", "")).strip() or template.template_name
    template.template_type = _template_type(body.get("template_type", template.template_type.value))
    template.product_category_ids = _as_uuid_list(
        body.get("product_category_ids"),
        field_name="product_category_ids",
    )
    structure_locked_at = _now()
    template.confirmed = True
    template.structure_locked_at = structure_locked_at
    template.structure_locked_by = operator_id

    chapters_payload = body.get("chapters")
    if not isinstance(chapters_payload, list):
        raise TemplateConfirmServiceError(
            "chapters must be a list",
            code="INVALID_INPUT",
            status_code=422,
        )
    chapters_by_temp = _replace_chapters(db, template=template, chapters=chapters_payload)

    db.query(TemplateMaterial).filter(TemplateMaterial.template_id == template.template_id).delete(
        synchronize_session=False
    )
    db.query(CandidateKnowledgeStub).filter(
        CandidateKnowledgeStub.template_id == template.template_id
    ).delete(synchronize_session=False)

    materials_payload = body.get("materials")
    if materials_payload is None:
        materials_payload = []
    if not isinstance(materials_payload, list):
        raise TemplateConfirmServiceError(
            "materials must be a list",
            code="INVALID_INPUT",
            status_code=422,
        )
    material_by_temp: dict[str, TemplateMaterial] = {}
    for material in materials_payload:
        if bool(material.get("ignored", False)):
            continue
        temp_id = str(material.get("temp_id", "")).strip()
        chapter_ref = material.get("chapter_temp_id")
        chapter_row = chapters_by_temp.get(str(chapter_ref)) if chapter_ref else None
        row = TemplateMaterial(
            kb_id=template.kb_id,
            template_id=template.template_id,
            template_chapter_id=chapter_row.template_chapter_id if chapter_row else None,
            import_id=task.import_id,
            material_type=_material_type(material.get("material_type", "other")),
            title=str(material.get("title", "")).strip() or None,
            summary=material.get("summary"),
            content=material.get("content"),
            product_category_ids=_as_uuid_list(
                material.get("product_category_ids"),
                field_name="material.product_category_ids",
            ),
            extract_as_candidate=bool(material.get("extract_as_candidate", False)),
        )
        db.add(row)
        db.flush()
        if temp_id:
            material_by_temp[temp_id] = row

    suggestion = (
        db.query(TemplateParseSuggestion)
        .filter(TemplateParseSuggestion.parse_task_id == parse_task_id)
        .one_or_none()
    )
    suggested_candidates = suggestion.suggested_candidates if suggestion else []
    candidate_payload_by_temp: dict[str, dict[str, Any]] = {}
    if isinstance(suggested_candidates, list):
        for candidate in suggested_candidates:
            temp_id = str(candidate.get("temp_id", "")).strip()
            if temp_id:
                candidate_payload_by_temp[temp_id] = candidate

    candidate_actions = body.get("candidate_actions")
    if candidate_actions is None:
        candidate_actions = []
    if not isinstance(candidate_actions, list):
        raise TemplateConfirmServiceError(
            "candidate_actions must be a list",
            code="INVALID_INPUT",
            status_code=422,
        )

    created_stub_count = 0
    for action in candidate_actions:
        if not bool(action.get("accepted", False)):
            continue
        temp_id = str(action.get("temp_id", "")).strip()
        if not temp_id:
            raise TemplateConfirmServiceError(
                "candidate_actions item missing temp_id",
                code="INVALID_INPUT",
                status_code=422,
            )
        material_temp = temp_id[2:] if temp_id.startswith("c_") else temp_id
        material_row = material_by_temp.get(material_temp) or material_by_temp.get(temp_id)
        candidate_payload = candidate_payload_by_temp.get(temp_id, {})
        chapter_temp = candidate_payload.get("chapter_temp_id")
        chapter_row = chapters_by_temp.get(str(chapter_temp)) if chapter_temp else None
        if chapter_row is None and material_row and material_row.template_chapter_id:
            chapter_row = (
                db.query(TemplateChapter)
                .filter(TemplateChapter.template_chapter_id == material_row.template_chapter_id)
                .one_or_none()
            )

        title = (
            str(candidate_payload.get("title", "")).strip()
            or (material_row.title if material_row and material_row.title else "")
            or f"Candidate {temp_id}"
        )
        summary = candidate_payload.get("summary") or (material_row.summary if material_row else None)
        content_preview = candidate_payload.get("content_preview") or (
            material_row.content if material_row else None
        )
        product_category_ids = _as_uuid_list(
            action.get("product_category_ids")
            or candidate_payload.get("product_category_ids")
            or (chapter_row.product_category_ids if chapter_row else []),
            field_name="candidate.product_category_ids",
        )
        chapter_taxonomy_id = _as_uuid(
            action.get("chapter_taxonomy_id") or candidate_payload.get("chapter_taxonomy_id"),
            field_name="chapter_taxonomy_id",
        )
        if chapter_taxonomy_id is None and chapter_row:
            chapter_taxonomy_id = chapter_row.chapter_taxonomy_id
        knowledge_type = action.get("knowledge_type") or candidate_payload.get(
            "suggested_knowledge_type"
        )
        suggestion_source = candidate_payload.get("suggestion_source")
        try:
            classification_confidence = float(candidate_payload.get("classification_confidence"))
        except (TypeError, ValueError):
            classification_confidence = None
        db.add(
            CandidateKnowledgeStub(
                kb_id=template.kb_id,
                import_id=task.import_id,
                template_id=template.template_id,
                template_chapter_id=chapter_row.template_chapter_id if chapter_row else None,
                material_id=material_row.material_id if material_row else None,
                candidate_type=_candidate_type(action.get("candidate_type")),
                title=title,
                summary=summary,
                content_preview=content_preview,
                product_category_ids=product_category_ids,
                chapter_taxonomy_id=chapter_taxonomy_id,
                suggested_knowledge_type=str(knowledge_type) if knowledge_type else None,
                suggestion_source=str(suggestion_source) if suggestion_source else None,
                classification_confidence=classification_confidence,
                chunk_ref=temp_id,
            )
        )
        created_stub_count += 1

    task.status = TemplateParseTaskStatus.confirmed
    task.finished_at = _now()

    db.add(
        TemplateAuditLog(
            trace_id=trace_id,
            kb_id=template.kb_id,
            template_id=template.template_id,
            template_library_id=template.template_library_id,
            import_id=template.source_import_id,
            operator_id=operator_id,
            action=TemplateAuditAction.confirm,
            payload_summary={
                "parse_task_id": str(task.parse_task_id),
                "candidate_stubs_created": created_stub_count,
            },
        )
    )
    db.commit()
    return ConfirmParseResult(
        parse_task_id=task.parse_task_id,
        template_id=template.template_id,
        template_library_id=template.template_library_id,
        status=task.status.value,
        structure_locked_at=structure_locked_at,
        candidate_stubs_created=created_stub_count,
    )
