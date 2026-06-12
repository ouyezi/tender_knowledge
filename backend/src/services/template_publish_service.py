from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.template import Template, TemplateStatus
from src.models.template_audit_log import TemplateAuditAction, TemplateAuditLog
from src.models.template_chapter import TemplateChapter
from src.models.template_library import TemplateLibrary, TemplateLibraryStatus
from src.models.template_material import TemplateMaterial
from src.models.template_publish_snapshot import (
    TemplatePublishObjectType,
    TemplatePublishSnapshot,
)
from src.models.template_rule import TemplateRule, TemplateRuleStatus, TemplateRuleType
from src.models.template_variable import TemplateVariable, TemplateVariableStatus


class TemplatePublishServiceError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


@dataclass
class PublishResult:
    object_id: UUID
    object_type: str
    status: str
    version: str
    version_no: int
    snapshot_id: UUID
    published_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_template_publishable(db: Session, template: Template) -> None:
    if not template.confirmed:
        raise TemplatePublishServiceError(
            "Template must be confirmed before publish",
            code="INVALID_STATE",
            status_code=422,
        )

    chapters = (
        db.query(TemplateChapter)
        .filter(
            TemplateChapter.template_id == template.template_id,
            TemplateChapter.ignored.is_(False),
        )
        .all()
    )
    if not chapters:
        raise TemplatePublishServiceError(
            "Template chapter tree cannot be empty",
            code="INVALID_STATE",
            status_code=422,
        )

    required_variables = (
        db.query(TemplateVariable)
        .filter(
            TemplateVariable.template_id == template.template_id,
            TemplateVariable.status == TemplateVariableStatus.active,
            TemplateVariable.required.is_(True),
        )
        .all()
    )
    missing_defaults = [
        item.variable_key
        for item in required_variables
        if not str(item.default_value or "").strip()
    ]
    if missing_defaults:
        raise TemplatePublishServiceError(
            f"Required variables missing default value: {', '.join(missing_defaults)}",
            code="INVALID_STATE",
            status_code=422,
        )

    required_chapter_ids = {
        chapter.template_chapter_id for chapter in chapters if chapter.required
    }
    if required_chapter_ids:
        required_rules = (
            db.query(TemplateRule)
            .filter(
                TemplateRule.template_id == template.template_id,
                TemplateRule.rule_type == TemplateRuleType.required,
                TemplateRule.status == TemplateRuleStatus.active,
            )
            .all()
        )
        covered = {
            rule.template_chapter_id
            for rule in required_rules
            if rule.template_chapter_id in required_chapter_ids
        }
        if not covered and required_chapter_ids:
            raise TemplatePublishServiceError(
                "Required chapter rules are missing",
                code="INVALID_STATE",
                status_code=422,
            )


def _snapshot_template(db: Session, template: Template) -> dict:
    chapters = (
        db.query(TemplateChapter)
        .filter(TemplateChapter.template_id == template.template_id)
        .order_by(TemplateChapter.level.asc(), TemplateChapter.sort_order.asc())
        .all()
    )
    materials = (
        db.query(TemplateMaterial)
        .filter(TemplateMaterial.template_id == template.template_id)
        .all()
    )
    variables = (
        db.query(TemplateVariable)
        .filter(TemplateVariable.template_id == template.template_id)
        .all()
    )
    rules = db.query(TemplateRule).filter(TemplateRule.template_id == template.template_id).all()
    return {
        "template": {
            "template_id": str(template.template_id),
            "template_library_id": str(template.template_library_id) if template.template_library_id else None,
            "template_name": template.template_name,
            "template_type": template.template_type.value,
            "product_category_ids": [str(item) for item in (template.product_category_ids or [])],
            "status": template.status.value,
            "version": template.version,
            "version_no": template.version_no,
        },
        "chapters": [
            {
                "template_chapter_id": str(row.template_chapter_id),
                "parent_id": str(row.parent_id) if row.parent_id else None,
                "title": row.title,
                "level": row.level,
                "sort_order": row.sort_order,
                "required": row.required,
                "ignored": row.ignored,
            }
            for row in chapters
        ],
        "materials": [
            {
                "material_id": str(row.material_id),
                "template_chapter_id": str(row.template_chapter_id) if row.template_chapter_id else None,
                "material_type": row.material_type.value,
                "title": row.title,
            }
            for row in materials
        ],
        "variables": [
            {
                "variable_id": str(row.variable_id),
                "template_chapter_id": str(row.template_chapter_id) if row.template_chapter_id else None,
                "variable_key": row.variable_key,
                "required": row.required,
                "default_value": row.default_value,
                "status": row.status.value,
            }
            for row in variables
        ],
        "rules": [
            {
                "rule_id": str(row.rule_id),
                "template_chapter_id": str(row.template_chapter_id) if row.template_chapter_id else None,
                "rule_type": row.rule_type.value,
                "status": row.status.value,
            }
            for row in rules
        ],
    }


def _snapshot_library(db: Session, library: TemplateLibrary) -> dict:
    templates = (
        db.query(Template)
        .filter(
            Template.template_library_id == library.template_library_id,
            Template.status == TemplateStatus.published,
        )
        .all()
    )
    return {
        "template_library": {
            "template_library_id": str(library.template_library_id),
            "library_name": library.library_name,
            "library_type": library.library_type.value,
            "product_category_ids": [str(item) for item in (library.product_category_ids or [])],
            "status": library.status.value,
            "version": library.version,
            "version_no": library.version_no,
        },
        "templates": [
            {
                "template_id": str(row.template_id),
                "template_name": row.template_name,
                "template_type": row.template_type.value,
                "version": row.version,
                "version_no": row.version_no,
            }
            for row in templates
        ],
    }


def _bump_version_if_republish(status: str, version_no: int) -> tuple[int, str]:
    if status == "published":
        next_no = max(version_no, 1) + 1
        return next_no, f"{next_no}.0"
    keep_no = max(version_no, 1)
    return keep_no, f"{keep_no}.0"


def publish_template(
    db: Session,
    *,
    kb_id: UUID,
    template_id: UUID,
    operator_id: str,
    trace_id: UUID,
) -> PublishResult:
    template = (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_id == template_id)
        .one_or_none()
    )
    if template is None:
        raise TemplatePublishServiceError("Template not found", code="NOT_FOUND", status_code=404)

    _ensure_template_publishable(db, template)
    next_version_no, next_version = _bump_version_if_republish(
        template.status.value, template.version_no
    )
    published_at = _now()
    template.status = TemplateStatus.published
    template.version_no = next_version_no
    template.version = next_version
    template.published_at = published_at
    template.published_by = operator_id

    snapshot = TemplatePublishSnapshot(
        kb_id=kb_id,
        object_type=TemplatePublishObjectType.template,
        object_id=template.template_id,
        version=template.version,
        version_no=template.version_no,
        snapshot_json=_snapshot_template(db, template),
        published_by=operator_id,
        published_at=published_at,
    )
    db.add(snapshot)
    db.add(
        TemplateAuditLog(
            trace_id=trace_id,
            kb_id=kb_id,
            template_id=template.template_id,
            template_library_id=template.template_library_id,
            import_id=template.source_import_id,
            operator_id=operator_id,
            action=TemplateAuditAction.publish,
            payload_summary={"snapshot_id": str(snapshot.snapshot_id), "object_type": "template"},
        )
    )
    db.commit()
    return PublishResult(
        object_id=template.template_id,
        object_type="template",
        status=template.status.value,
        version=template.version,
        version_no=template.version_no,
        snapshot_id=snapshot.snapshot_id,
        published_at=published_at,
    )


def publish_template_library(
    db: Session,
    *,
    kb_id: UUID,
    template_library_id: UUID,
    operator_id: str,
    trace_id: UUID,
    cascade_templates: bool = True,
) -> PublishResult:
    library = (
        db.query(TemplateLibrary)
        .filter(
            TemplateLibrary.kb_id == kb_id,
            TemplateLibrary.template_library_id == template_library_id,
        )
        .one_or_none()
    )
    if library is None:
        raise TemplatePublishServiceError(
            "Template library not found",
            code="NOT_FOUND",
            status_code=404,
        )

    templates = (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_library_id == template_library_id)
        .all()
    )
    if not templates:
        raise TemplatePublishServiceError(
            "Template library cannot be empty",
            code="INVALID_STATE",
            status_code=422,
        )

    for template in templates:
        _ensure_template_publishable(db, template)
        if cascade_templates:
            template.status = TemplateStatus.published
            template.published_at = _now()
            template.published_by = operator_id

    next_version_no, next_version = _bump_version_if_republish(
        library.status.value, library.version_no
    )
    published_at = _now()
    library.status = TemplateLibraryStatus.published
    library.version_no = next_version_no
    library.version = next_version
    library.published_at = published_at
    library.published_by = operator_id

    snapshot = TemplatePublishSnapshot(
        kb_id=kb_id,
        object_type=TemplatePublishObjectType.template_library,
        object_id=library.template_library_id,
        version=library.version,
        version_no=library.version_no,
        snapshot_json=_snapshot_library(db, library),
        published_by=operator_id,
        published_at=published_at,
    )
    db.add(snapshot)
    db.add(
        TemplateAuditLog(
            trace_id=trace_id,
            kb_id=kb_id,
            template_library_id=library.template_library_id,
            operator_id=operator_id,
            action=TemplateAuditAction.publish,
            payload_summary={"snapshot_id": str(snapshot.snapshot_id), "object_type": "template_library"},
        )
    )
    db.commit()
    return PublishResult(
        object_id=library.template_library_id,
        object_type="template_library",
        status=library.status.value,
        version=library.version,
        version_no=library.version_no,
        snapshot_id=snapshot.snapshot_id,
        published_at=published_at,
    )
