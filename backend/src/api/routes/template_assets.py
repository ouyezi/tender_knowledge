from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.deps import get_kb_or_404, get_operator_id, kb_write_guard
from src.api.envelope import error, success
from src.api.middleware.audit import get_trace_id
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase
from src.models.template import Template
from src.models.template_audit_log import TemplateAuditAction, TemplateAuditLog
from src.models.template_chapter import TemplateChapter
from src.models.template_material import (
    TemplateMaterial,
    TemplateMaterialStatus,
    TemplateMaterialType,
)
from src.models.template_rule import (
    TemplateRule,
    TemplateRuleAction,
    TemplateRuleStatus,
    TemplateRuleType,
)
from src.models.template_variable import (
    TemplateVariable,
    TemplateVariableStatus,
    TemplateVariableValueType,
)

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/templates/{template_id}",
    tags=["template-assets"],
)


class MaterialCreateRequest(BaseModel):
    template_chapter_id: UUID | None = None
    material_type: TemplateMaterialType
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    import_id: UUID | None = None
    storage_path: str | None = None
    product_category_ids: list[UUID] = Field(default_factory=list)
    extract_as_candidate: bool = False


class MaterialPatchRequest(BaseModel):
    template_chapter_id: UUID | None = None
    material_type: TemplateMaterialType | None = None
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    storage_path: str | None = None
    product_category_ids: list[UUID] | None = None
    extract_as_candidate: bool | None = None
    status: TemplateMaterialStatus | None = None


class VariableCreateRequest(BaseModel):
    template_chapter_id: UUID | None = None
    variable_key: str
    display_name: str | None = None
    value_type: TemplateVariableValueType = TemplateVariableValueType.string
    required: bool = False
    default_value: str | None = None
    description: str | None = None
    options: list[str] = Field(default_factory=list)


class VariablePatchRequest(BaseModel):
    template_chapter_id: UUID | None = None
    display_name: str | None = None
    value_type: TemplateVariableValueType | None = None
    required: bool | None = None
    default_value: str | None = None
    description: str | None = None
    options: list[str] | None = None
    status: TemplateVariableStatus | None = None


class RuleCreateRequest(BaseModel):
    template_chapter_id: UUID | None = None
    rule_type: TemplateRuleType
    condition: dict[str, object] | None = None
    action: TemplateRuleAction = TemplateRuleAction.enable
    message: str | None = None


class RulePatchRequest(BaseModel):
    template_chapter_id: UUID | None = None
    condition: dict[str, object] | None = None
    action: TemplateRuleAction | None = None
    message: str | None = None
    status: TemplateRuleStatus | None = None


MVP_RULE_TYPES = {TemplateRuleType.required, TemplateRuleType.optional, TemplateRuleType.product_match}


def _serialize_material(row: TemplateMaterial) -> dict[str, object]:
    return {
        "material_id": str(row.material_id),
        "template_chapter_id": str(row.template_chapter_id) if row.template_chapter_id else None,
        "material_type": row.material_type.value,
        "title": row.title,
        "summary": row.summary,
        "content": row.content,
        "import_id": str(row.import_id) if row.import_id else None,
        "storage_path": row.storage_path,
        "product_category_ids": [str(item) for item in (row.product_category_ids or [])],
        "extract_as_candidate": row.extract_as_candidate,
        "status": row.status.value,
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_variable(row: TemplateVariable) -> dict[str, object]:
    return {
        "variable_id": str(row.variable_id),
        "template_chapter_id": str(row.template_chapter_id) if row.template_chapter_id else None,
        "variable_key": row.variable_key,
        "display_name": row.display_name,
        "value_type": row.value_type.value,
        "required": row.required,
        "default_value": row.default_value,
        "description": row.description,
        "options": row.options or [],
        "status": row.status.value,
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_rule(row: TemplateRule) -> dict[str, object]:
    return {
        "rule_id": str(row.rule_id),
        "template_chapter_id": str(row.template_chapter_id) if row.template_chapter_id else None,
        "rule_type": row.rule_type.value,
        "condition": row.condition,
        "action": row.action.value,
        "message": row.message,
        "status": row.status.value,
        "updated_at": row.updated_at.isoformat(),
    }


def _get_template(db: Session, kb_id: UUID, template_id: UUID) -> Template | None:
    return (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_id == template_id)
        .one_or_none()
    )


def _ensure_chapter_belongs_template(
    db: Session,
    template_id: UUID,
    template_chapter_id: UUID | None,
) -> bool:
    if template_chapter_id is None:
        return True
    chapter = (
        db.query(TemplateChapter)
        .filter(
            TemplateChapter.template_id == template_id,
            TemplateChapter.template_chapter_id == template_chapter_id,
        )
        .one_or_none()
    )
    return chapter is not None


def _write_audit(
    db: Session,
    *,
    template: Template,
    operator_id: str,
    action: TemplateAuditAction,
    payload_summary: dict[str, object],
):
    db.add(
        TemplateAuditLog(
            trace_id=get_trace_id() or UUID(int=0),
            kb_id=template.kb_id,
            template_id=template.template_id,
            template_library_id=template.template_library_id,
            import_id=template.source_import_id,
            operator_id=operator_id,
            action=action,
            payload_summary=payload_summary,
        )
    )


@router.get("/materials")
def list_materials(
    kb_id: UUID,
    template_id: UUID,
    template_chapter_id: UUID | None = None,
    material_type: TemplateMaterialType | None = None,
    status: TemplateMaterialStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    offset = max(page - 1, 0) * page_size
    query = db.query(TemplateMaterial).filter(TemplateMaterial.template_id == template_id)
    if template_chapter_id:
        query = query.filter(TemplateMaterial.template_chapter_id == template_chapter_id)
    if material_type:
        query = query.filter(TemplateMaterial.material_type == material_type)
    if status:
        query = query.filter(TemplateMaterial.status == status)
    total = query.count()
    rows = (
        query.order_by(TemplateMaterial.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {"items": [_serialize_material(row) for row in rows], "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )


@router.post("/materials")
def create_material(
    kb_id: UUID,
    template_id: UUID,
    body: MaterialCreateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    if not _ensure_chapter_belongs_template(db, template_id, body.template_chapter_id):
        return JSONResponse(
            status_code=422,
            content=error("INVALID_INPUT", "template_chapter_id does not belong to template", trace_id=get_trace_id()),
        )
    row = TemplateMaterial(
        kb_id=kb_id,
        template_id=template_id,
        template_chapter_id=body.template_chapter_id,
        import_id=body.import_id,
        material_type=body.material_type,
        title=body.title,
        summary=body.summary,
        content=body.content,
        storage_path=body.storage_path,
        product_category_ids=[str(item) for item in body.product_category_ids],
        extract_as_candidate=body.extract_as_candidate,
    )
    db.add(row)
    db.flush()
    _write_audit(
        db,
        template=template,
        operator_id=operator_id,
        action=TemplateAuditAction.material_update,
        payload_summary={"material_id": str(row.material_id), "operation": "create"},
    )
    db.commit()
    return success(_serialize_material(row), trace_id=get_trace_id())


@router.patch("/materials/{material_id}")
def update_material(
    kb_id: UUID,
    template_id: UUID,
    material_id: UUID,
    body: MaterialPatchRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    row = (
        db.query(TemplateMaterial)
        .filter(TemplateMaterial.template_id == template_id, TemplateMaterial.material_id == material_id)
        .one_or_none()
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Material not found", trace_id=get_trace_id()),
        )
    patch = body.model_dump(exclude_unset=True)
    if "template_chapter_id" in patch and not _ensure_chapter_belongs_template(
        db, template_id, body.template_chapter_id
    ):
        return JSONResponse(
            status_code=422,
            content=error("INVALID_INPUT", "template_chapter_id does not belong to template", trace_id=get_trace_id()),
        )
    for key, value in patch.items():
        if key == "product_category_ids" and value is not None:
            setattr(row, key, [str(item) for item in value])
            continue
        setattr(row, key, value)
    _write_audit(
        db,
        template=template,
        operator_id=operator_id,
        action=TemplateAuditAction.material_update,
        payload_summary={"material_id": str(row.material_id), "operation": "update"},
    )
    db.commit()
    return success(_serialize_material(row), trace_id=get_trace_id())


@router.post("/materials/{material_id}/deprecate")
def deprecate_material(
    kb_id: UUID,
    template_id: UUID,
    material_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    return update_material(
        kb_id,
        template_id,
        material_id,
        MaterialPatchRequest(status=TemplateMaterialStatus.deprecated),
        db,
        _,
        operator_id,
    )


@router.get("/variables")
def list_variables(
    kb_id: UUID,
    template_id: UUID,
    template_chapter_id: UUID | None = None,
    status: TemplateVariableStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    offset = max(page - 1, 0) * page_size
    query = db.query(TemplateVariable).filter(TemplateVariable.template_id == template_id)
    if template_chapter_id:
        query = query.filter(TemplateVariable.template_chapter_id == template_chapter_id)
    if status:
        query = query.filter(TemplateVariable.status == status)
    total = query.count()
    rows = (
        query.order_by(TemplateVariable.updated_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return success(
        {"items": [_serialize_variable(row) for row in rows], "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )


@router.post("/variables")
def create_variable(
    kb_id: UUID,
    template_id: UUID,
    body: VariableCreateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    if not _ensure_chapter_belongs_template(db, template_id, body.template_chapter_id):
        return JSONResponse(
            status_code=422,
            content=error("INVALID_INPUT", "template_chapter_id does not belong to template", trace_id=get_trace_id()),
        )
    key = body.variable_key.strip()
    if not key:
        return JSONResponse(
            status_code=422,
            content=error("INVALID_INPUT", "variable_key is required", trace_id=get_trace_id()),
        )
    duplicate = (
        db.query(TemplateVariable)
        .filter(TemplateVariable.template_id == template_id, TemplateVariable.variable_key == key)
        .one_or_none()
    )
    if duplicate:
        return JSONResponse(
            status_code=409,
            content=error("CONFLICT", "variable_key already exists", trace_id=get_trace_id()),
        )
    row = TemplateVariable(
        kb_id=kb_id,
        template_id=template_id,
        template_chapter_id=body.template_chapter_id,
        variable_key=key,
        display_name=body.display_name,
        value_type=body.value_type,
        required=body.required,
        default_value=body.default_value,
        description=body.description,
        options=body.options,
    )
    db.add(row)
    db.flush()
    _write_audit(
        db,
        template=template,
        operator_id=operator_id,
        action=TemplateAuditAction.variable_update,
        payload_summary={"variable_id": str(row.variable_id), "operation": "create"},
    )
    db.commit()
    return success(_serialize_variable(row), trace_id=get_trace_id())


@router.patch("/variables/{variable_id}")
def update_variable(
    kb_id: UUID,
    template_id: UUID,
    variable_id: UUID,
    body: VariablePatchRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    row = (
        db.query(TemplateVariable)
        .filter(TemplateVariable.template_id == template_id, TemplateVariable.variable_id == variable_id)
        .one_or_none()
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Variable not found", trace_id=get_trace_id()),
        )
    if body.template_chapter_id and not _ensure_chapter_belongs_template(
        db, template_id, body.template_chapter_id
    ):
        return JSONResponse(
            status_code=422,
            content=error("INVALID_INPUT", "template_chapter_id does not belong to template", trace_id=get_trace_id()),
        )
    patch = body.model_dump(exclude_unset=True)
    for key, value in patch.items():
        setattr(row, key, value)
    _write_audit(
        db,
        template=template,
        operator_id=operator_id,
        action=TemplateAuditAction.variable_update,
        payload_summary={"variable_id": str(row.variable_id), "operation": "update"},
    )
    db.commit()
    return success(_serialize_variable(row), trace_id=get_trace_id())


@router.delete("/variables/{variable_id}")
def delete_variable(
    kb_id: UUID,
    template_id: UUID,
    variable_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    row = (
        db.query(TemplateVariable)
        .filter(TemplateVariable.template_id == template_id, TemplateVariable.variable_id == variable_id)
        .one_or_none()
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Variable not found", trace_id=get_trace_id()),
        )
    row.status = TemplateVariableStatus.inactive
    template = _get_template(db, kb_id, template_id)
    if template:
        _write_audit(
            db,
            template=template,
            operator_id=operator_id,
            action=TemplateAuditAction.variable_update,
            payload_summary={"variable_id": str(row.variable_id), "operation": "deactivate"},
        )
    db.commit()
    return success(_serialize_variable(row), trace_id=get_trace_id())


@router.get("/rules")
def list_rules(
    kb_id: UUID,
    template_id: UUID,
    template_chapter_id: UUID | None = None,
    rule_type: TemplateRuleType | None = None,
    status: TemplateRuleStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    offset = max(page - 1, 0) * page_size
    query = db.query(TemplateRule).filter(TemplateRule.template_id == template_id)
    if template_chapter_id:
        query = query.filter(TemplateRule.template_chapter_id == template_chapter_id)
    if rule_type:
        query = query.filter(TemplateRule.rule_type == rule_type)
    if status:
        query = query.filter(TemplateRule.status == status)
    total = query.count()
    rows = query.order_by(TemplateRule.updated_at.desc()).offset(offset).limit(page_size).all()
    return success(
        {"items": [_serialize_rule(row) for row in rows], "total": total, "page": page, "page_size": page_size},
        trace_id=get_trace_id(),
    )


@router.post("/rules")
def create_rule(
    kb_id: UUID,
    template_id: UUID,
    body: RuleCreateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    if body.rule_type not in MVP_RULE_TYPES:
        return JSONResponse(
            status_code=422,
            content=error("INVALID_RULE_TYPE", "Only MVP rule types are supported", trace_id=get_trace_id()),
        )
    if not _ensure_chapter_belongs_template(db, template_id, body.template_chapter_id):
        return JSONResponse(
            status_code=422,
            content=error("INVALID_INPUT", "template_chapter_id does not belong to template", trace_id=get_trace_id()),
        )
    row = TemplateRule(
        kb_id=kb_id,
        template_id=template_id,
        template_chapter_id=body.template_chapter_id,
        rule_type=body.rule_type,
        condition=body.condition,
        action=body.action,
        message=body.message,
    )
    db.add(row)
    db.flush()
    _write_audit(
        db,
        template=template,
        operator_id=operator_id,
        action=TemplateAuditAction.rule_update,
        payload_summary={"rule_id": str(row.rule_id), "operation": "create"},
    )
    db.commit()
    return success(_serialize_rule(row), trace_id=get_trace_id())


@router.patch("/rules/{rule_id}")
def update_rule(
    kb_id: UUID,
    template_id: UUID,
    rule_id: UUID,
    body: RulePatchRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    template = _get_template(db, kb_id, template_id)
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    row = (
        db.query(TemplateRule)
        .filter(TemplateRule.template_id == template_id, TemplateRule.rule_id == rule_id)
        .one_or_none()
    )
    if row is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Rule not found", trace_id=get_trace_id()),
        )
    if body.template_chapter_id and not _ensure_chapter_belongs_template(
        db, template_id, body.template_chapter_id
    ):
        return JSONResponse(
            status_code=422,
            content=error("INVALID_INPUT", "template_chapter_id does not belong to template", trace_id=get_trace_id()),
        )
    patch = body.model_dump(exclude_unset=True)
    for key, value in patch.items():
        setattr(row, key, value)
    _write_audit(
        db,
        template=template,
        operator_id=operator_id,
        action=TemplateAuditAction.rule_update,
        payload_summary={"rule_id": str(row.rule_id), "operation": "update"},
    )
    db.commit()
    return success(_serialize_rule(row), trace_id=get_trace_id())


@router.post("/rules/{rule_id}/deprecate")
def deprecate_rule(
    kb_id: UUID,
    template_id: UUID,
    rule_id: UUID,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    return update_rule(
        kb_id,
        template_id,
        rule_id,
        RulePatchRequest(status=TemplateRuleStatus.inactive),
        db,
        _,
        operator_id,
    )
