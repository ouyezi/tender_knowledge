from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import String, and_, or_, cast
from sqlalchemy.orm import Session

from src.models.knowledge_blueprint import BlueprintStatus, KnowledgeBlueprint
from src.models.knowledge_blueprint_node import ImportanceLevel, KnowledgeBlueprintNode
from src.services.knowledge.blueprint_field_utils import (
    CONTENT_DESCRIPTION_MAX,
    SUGGESTED_STRUCTURE_MD_MAX,
    TENDER_RESPONSE_HINT_MAX,
    truncate_blueprint_field,
)
from src.services.knowledge.blueprint_tree_utils import assign_node_codes, flatten_tree, nest_tree


class BlueprintConflictError(Exception):
    pass


class BlueprintValidationError(Exception):
    pass


class BlueprintNotFoundError(Exception):
    pass


def create_blueprint(db: Session, *, kb_id: UUID, payload: dict[str, Any]) -> KnowledgeBlueprint:
    _validate_name(payload.get("name"))
    source_node_id = _as_uuid(payload.get("source_node_id"), "source_node_id")
    if get_blueprint_by_source(db, kb_id=kb_id, source_node_id=source_node_id) is not None:
        raise BlueprintConflictError

    nested_nodes = _prepare_nested_nodes(payload)
    blueprint = KnowledgeBlueprint(
        kb_id=kb_id,
        name=str(payload.get("name") or "").strip(),
        description=payload.get("description"),
        source_doc_id=_as_uuid(payload.get("source_doc_id"), "source_doc_id"),
        source_node_id=source_node_id,
        source_chapter_title=payload.get("source_chapter_title"),
        product_tags=list(payload.get("product_tags") or []),
        industry_tags=list(payload.get("industry_tags") or []),
        scenario_tags=list(payload.get("scenario_tags") or []),
        applicable_project_type=list(payload.get("applicable_project_type") or []),
        related_regulations=list(payload.get("related_regulations") or []),
        overall_strategy=payload.get("overall_strategy"),
        common_mistakes=payload.get("common_mistakes"),
        template_style=payload.get("template_style"),
        usual_page_range=payload.get("usual_page_range"),
        suggested_structure_md=truncate_blueprint_field(
            payload.get("suggested_structure_md"),
            max_len=SUGGESTED_STRUCTURE_MD_MAX,
        ),
        status=BlueprintStatus(payload.get("status") or BlueprintStatus.active.value),
        version=int(payload.get("version") or 1),
    )
    db.add(blueprint)
    db.flush()

    replace_nodes(db, blueprint_id=blueprint.blueprint_id, flat_nodes=flatten_tree(nested_nodes))
    db.flush()
    return blueprint


def update_blueprint(
    db: Session,
    *,
    kb_id: UUID,
    blueprint_id: UUID,
    payload: dict[str, Any],
) -> KnowledgeBlueprint:
    blueprint = (
        db.query(KnowledgeBlueprint)
        .filter(
            KnowledgeBlueprint.kb_id == kb_id,
            KnowledgeBlueprint.blueprint_id == blueprint_id,
        )
        .one_or_none()
    )
    if blueprint is None:
        raise BlueprintNotFoundError

    name = payload.get("name", blueprint.name)
    _validate_name(name)

    blueprint.name = str(name).strip()
    blueprint.description = payload.get("description", blueprint.description)
    blueprint.source_doc_id = _as_uuid(payload.get("source_doc_id", blueprint.source_doc_id), "source_doc_id")
    blueprint.source_node_id = _as_uuid(
        payload.get("source_node_id", blueprint.source_node_id), "source_node_id"
    )
    blueprint.source_chapter_title = payload.get("source_chapter_title", blueprint.source_chapter_title)
    blueprint.product_tags = list(payload.get("product_tags", blueprint.product_tags) or [])
    blueprint.industry_tags = list(payload.get("industry_tags", blueprint.industry_tags) or [])
    blueprint.scenario_tags = list(payload.get("scenario_tags", blueprint.scenario_tags) or [])
    blueprint.applicable_project_type = list(
        payload.get("applicable_project_type", blueprint.applicable_project_type) or []
    )
    blueprint.related_regulations = list(
        payload.get("related_regulations", blueprint.related_regulations) or []
    )
    blueprint.overall_strategy = payload.get("overall_strategy", blueprint.overall_strategy)
    blueprint.common_mistakes = payload.get("common_mistakes", blueprint.common_mistakes)
    blueprint.template_style = payload.get("template_style", blueprint.template_style)
    blueprint.usual_page_range = payload.get("usual_page_range", blueprint.usual_page_range)
    if "suggested_structure_md" in payload:
        blueprint.suggested_structure_md = truncate_blueprint_field(
            payload.get("suggested_structure_md"),
            max_len=SUGGESTED_STRUCTURE_MD_MAX,
        )
    if "status" in payload and payload.get("status") is not None:
        blueprint.status = BlueprintStatus(str(payload.get("status")))
    if "version" in payload and payload.get("version") is not None:
        blueprint.version = int(payload.get("version"))
    else:
        blueprint.version = int(blueprint.version) + 1

    if "nodes" in payload:
        nested_nodes = _prepare_nested_nodes(payload)
        replace_nodes(db, blueprint_id=blueprint.blueprint_id, flat_nodes=flatten_tree(nested_nodes))
    db.flush()
    return blueprint


def replace_nodes(db: Session, *, blueprint_id: UUID, flat_nodes: list[dict[str, Any]]) -> None:
    db.query(KnowledgeBlueprintNode).filter(
        KnowledgeBlueprintNode.blueprint_id == blueprint_id
    ).delete(synchronize_session=False)

    id_map = {node["temp_id"]: uuid4() for node in flat_nodes}
    for index, node in enumerate(flat_nodes):
        node_id = id_map[node["temp_id"]]
        parent_temp_id = node.get("parent_temp_id")
        parent_id = id_map.get(parent_temp_id) if parent_temp_id else None
        importance = node.get("importance_level") or ImportanceLevel.optional
        db.add(
            KnowledgeBlueprintNode(
                node_id=node_id,
                blueprint_id=blueprint_id,
                parent_node_id=parent_id,
                node_code=node.get("node_code"),
                node_title=str(node.get("node_title") or ""),
                node_level=int(node.get("node_level") or 1),
                node_order=int(node.get("node_order") if node.get("node_order") is not None else index + 1),
                purpose=node.get("purpose"),
                writing_goal=node.get("writing_goal"),
                writing_hint=node.get("writing_hint"),
                content_description=truncate_blueprint_field(
                    node.get("content_description"),
                    max_len=CONTENT_DESCRIPTION_MAX,
                ),
                tender_response_hint=truncate_blueprint_field(
                    node.get("tender_response_hint"),
                    max_len=TENDER_RESPONSE_HINT_MAX,
                ),
                importance_level=_coerce_importance_level(importance),
                content_type=node.get("content_type"),
                keyword_hint=list(node.get("keyword_hint") or []),
            )
        )


def get_blueprint_by_source(
    db: Session, *, kb_id: UUID, source_node_id: UUID
) -> KnowledgeBlueprint | None:
    return (
        db.query(KnowledgeBlueprint)
        .filter(
            KnowledgeBlueprint.kb_id == kb_id,
            KnowledgeBlueprint.source_node_id == source_node_id,
        )
        .one_or_none()
    )


def get_blueprint_detail(db: Session, *, kb_id: UUID, blueprint_id: UUID) -> dict[str, Any]:
    blueprint = (
        db.query(KnowledgeBlueprint)
        .filter(
            KnowledgeBlueprint.kb_id == kb_id,
            KnowledgeBlueprint.blueprint_id == blueprint_id,
        )
        .one_or_none()
    )
    if blueprint is None:
        raise BlueprintNotFoundError

    node_rows = (
        db.query(KnowledgeBlueprintNode)
        .filter(KnowledgeBlueprintNode.blueprint_id == blueprint_id)
        .order_by(KnowledgeBlueprintNode.node_order.asc(), KnowledgeBlueprintNode.created_at.asc())
        .all()
    )
    flat_nodes = [
        {
            "temp_id": str(node.node_id),
            "parent_temp_id": str(node.parent_node_id) if node.parent_node_id else None,
            "node_id": str(node.node_id),
            "node_code": node.node_code,
            "node_title": node.node_title,
            "node_level": node.node_level,
            "node_order": node.node_order,
            "purpose": node.purpose,
            "writing_goal": node.writing_goal,
            "writing_hint": node.writing_hint,
            "content_description": node.content_description,
            "tender_response_hint": node.tender_response_hint,
            "importance_level": node.importance_level.value,
            "content_type": node.content_type,
            "keyword_hint": node.keyword_hint or [],
        }
        for node in node_rows
    ]
    return {
        "blueprint_id": str(blueprint.blueprint_id),
        "kb_id": str(blueprint.kb_id),
        "name": blueprint.name,
        "description": blueprint.description,
        "source_doc_id": str(blueprint.source_doc_id),
        "source_node_id": str(blueprint.source_node_id),
        "source_chapter_title": blueprint.source_chapter_title,
        "product_tags": blueprint.product_tags or [],
        "industry_tags": blueprint.industry_tags or [],
        "scenario_tags": blueprint.scenario_tags or [],
        "applicable_project_type": blueprint.applicable_project_type or [],
        "related_regulations": blueprint.related_regulations or [],
        "overall_strategy": blueprint.overall_strategy,
        "common_mistakes": blueprint.common_mistakes,
        "template_style": blueprint.template_style,
        "usual_page_range": blueprint.usual_page_range,
        "suggested_structure_md": blueprint.suggested_structure_md,
        "status": blueprint.status.value,
        "version": blueprint.version,
        "nodes": nest_tree(flat_nodes),
    }


def list_blueprints(
    db: Session,
    *,
    kb_id: UUID,
    keyword: str | None,
    product_tags: list[str] | None,
    industry_tags: list[str] | None,
    scenario_tags: list[str] | None,
    page: int,
    page_size: int,
) -> tuple[list[KnowledgeBlueprint], int]:
    query = db.query(KnowledgeBlueprint).filter(KnowledgeBlueprint.kb_id == kb_id)
    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        query = query.filter(
            or_(
                KnowledgeBlueprint.name.ilike(pattern),
                KnowledgeBlueprint.description.ilike(pattern),
            )
        )
    query = _apply_tag_filter(query, KnowledgeBlueprint.product_tags, product_tags)
    query = _apply_tag_filter(query, KnowledgeBlueprint.industry_tags, industry_tags)
    query = _apply_tag_filter(query, KnowledgeBlueprint.scenario_tags, scenario_tags)

    total = query.count()
    page_num = max(int(page or 1), 1)
    size = max(int(page_size or 10), 1)
    rows = (
        query.order_by(KnowledgeBlueprint.updated_at.desc(), KnowledgeBlueprint.created_at.desc())
        .offset((page_num - 1) * size)
        .limit(size)
        .all()
    )
    return rows, total


def delete_blueprint(db: Session, *, kb_id: UUID, blueprint_id: UUID) -> None:
    blueprint = (
        db.query(KnowledgeBlueprint)
        .filter(
            KnowledgeBlueprint.kb_id == kb_id,
            KnowledgeBlueprint.blueprint_id == blueprint_id,
        )
        .one_or_none()
    )
    if blueprint is None:
        raise BlueprintNotFoundError
    db.query(KnowledgeBlueprintNode).filter(
        KnowledgeBlueprintNode.blueprint_id == blueprint.blueprint_id
    ).delete(synchronize_session=False)
    db.delete(blueprint)
    db.flush()


def delete_blueprints_by_doc_id(db: Session, *, doc_id: UUID) -> int:
    blueprints = (
        db.query(KnowledgeBlueprint)
        .filter(KnowledgeBlueprint.source_doc_id == doc_id)
        .all()
    )
    if not blueprints:
        return 0
    blueprint_ids = [item.blueprint_id for item in blueprints]
    db.query(KnowledgeBlueprintNode).filter(
        KnowledgeBlueprintNode.blueprint_id.in_(blueprint_ids)
    ).delete(synchronize_session=False)
    deleted = (
        db.query(KnowledgeBlueprint)
        .filter(KnowledgeBlueprint.blueprint_id.in_(blueprint_ids))
        .delete(synchronize_session=False)
    )
    db.flush()
    return int(deleted)


def _prepare_nested_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    nested_nodes = deepcopy(payload.get("nodes") or [])
    assign_node_codes(nested_nodes)
    flat_nodes = flatten_tree(nested_nodes)
    if not any(int(node.get("node_level") or 0) == 1 for node in flat_nodes):
        raise BlueprintValidationError
    return nested_nodes


def _validate_name(name: Any) -> None:
    if not str(name or "").strip():
        raise BlueprintValidationError


def _as_uuid(raw: Any, field_name: str) -> UUID:
    if isinstance(raw, UUID):
        return raw
    if raw is None:
        raise BlueprintValidationError(f"{field_name} is required")
    return UUID(str(raw))


def _coerce_importance_level(raw: str | ImportanceLevel) -> ImportanceLevel:
    if isinstance(raw, ImportanceLevel):
        return raw
    return ImportanceLevel(str(raw))


def _apply_tag_filter(query, column, tags: list[str] | None):
    normalized = [str(item).strip() for item in (tags or []) if str(item).strip()]
    if not normalized:
        return query
    conditions = [cast(column, String).ilike(f'%"{tag}"%') for tag in normalized]
    return query.filter(and_(*conditions))
