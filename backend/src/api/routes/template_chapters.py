from datetime import datetime, timezone
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

router = APIRouter(
    prefix="/api/v1/kbs/{kb_id}/templates/{template_id}/chapters",
    tags=["template-chapters"],
)


class BatchUpdateChapterItem(BaseModel):
    template_chapter_id: UUID
    parent_id: UUID | None = None
    title: str
    level: int = Field(ge=1, le=9)
    sort_order: int = 0
    chapter_taxonomy_id: UUID | None = None
    product_category_ids: list[UUID] = Field(default_factory=list)
    required: bool = False
    is_fixed_section: bool = False
    ignored: bool = False


class BatchUpdateRequest(BaseModel):
    expected_template_updated_at: datetime | None = None
    chapters: list[BatchUpdateChapterItem]


def _serialize_chapter(chapter: TemplateChapter) -> dict[str, object]:
    return {
        "template_chapter_id": str(chapter.template_chapter_id),
        "title": chapter.title,
        "level": chapter.level,
        "sort_order": chapter.sort_order,
        "parent_id": str(chapter.parent_id) if chapter.parent_id else None,
        "chapter_taxonomy_id": str(chapter.chapter_taxonomy_id) if chapter.chapter_taxonomy_id else None,
        "product_category_ids": [str(item) for item in (chapter.product_category_ids or [])],
        "required": chapter.required,
        "is_fixed_section": chapter.is_fixed_section,
        "ignored": chapter.ignored,
        "status": chapter.status.value,
        "bound_material_ids": [str(item) for item in (chapter.bound_material_ids or [])],
        "variable_ids": [str(item) for item in (chapter.variable_ids or [])],
        "rule_ids": [str(item) for item in (chapter.rule_ids or [])],
        "children": [],
    }


def _build_nested_tree(chapters: list[TemplateChapter]) -> list[dict[str, object]]:
    nodes: dict[UUID, dict[str, object]] = {}
    roots: list[dict[str, object]] = []
    for chapter in chapters:
        nodes[chapter.template_chapter_id] = _serialize_chapter(chapter)

    for chapter in chapters:
        node = nodes[chapter.template_chapter_id]
        if chapter.parent_id is None:
            roots.append(node)
            continue
        parent = nodes.get(chapter.parent_id)
        if parent is None:
            roots.append(node)
            continue
        parent["children"].append(node)

    return roots


def _validate_batch_tree(
    chapters: list[BatchUpdateChapterItem],
    existing_ids: set[UUID],
) -> tuple[dict[UUID, BatchUpdateChapterItem], str | None]:
    if not chapters:
        return {}, "chapters cannot be empty"

    by_id: dict[UUID, BatchUpdateChapterItem] = {}
    for item in chapters:
        if item.template_chapter_id in by_id:
            return {}, f"duplicate chapter id: {item.template_chapter_id}"
        by_id[item.template_chapter_id] = item

    missing = [str(chapter_id) for chapter_id in by_id if chapter_id not in existing_ids]
    if missing:
        return {}, f"unknown chapter id(s): {', '.join(missing)}"
    if len(by_id) != len(existing_ids):
        return {}, "chapters must contain all existing chapter nodes"

    for item in chapters:
        if item.parent_id is None:
            if item.level != 1:
                return {}, f"root chapter level must be 1: {item.template_chapter_id}"
            continue
        if item.parent_id == item.template_chapter_id:
            return {}, f"chapter cannot be parent of itself: {item.template_chapter_id}"
        parent = by_id.get(item.parent_id)
        if parent is None:
            return {}, f"parent not found in payload: {item.parent_id}"
        if item.level != parent.level + 1:
            return (
                {},
                "invalid level relationship between "
                f"{item.template_chapter_id} and parent {item.parent_id}",
            )

    for item in chapters:
        seen: set[UUID] = set()
        current = item
        while current.parent_id is not None:
            if current.parent_id in seen:
                return {}, f"cycle detected at chapter: {item.template_chapter_id}"
            seen.add(current.parent_id)
            parent = by_id.get(current.parent_id)
            if parent is None:
                break
            current = parent
    return by_id, None


@router.get("/tree")
def get_chapter_tree(
    kb_id: UUID,
    template_id: UUID,
    format: str = "nested",
    include_ignored: bool = False,
    status: str | None = None,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    _ = format
    template = (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_id == template_id)
        .one_or_none()
    )
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    query = db.query(TemplateChapter).filter(TemplateChapter.template_id == template_id)
    if not include_ignored:
        query = query.filter(TemplateChapter.ignored.is_(False))
    if status:
        query = query.filter(TemplateChapter.status == status)
    chapters = query.order_by(TemplateChapter.level.asc(), TemplateChapter.sort_order.asc()).all()
    roots = _build_nested_tree(chapters)
    return success(
        {"template_id": str(template_id), "roots": roots},
        trace_id=get_trace_id(),
    )


@router.post("/batch-update")
def batch_update_chapter_tree(
    kb_id: UUID,
    template_id: UUID,
    body: BatchUpdateRequest,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(kb_write_guard),
    operator_id: str = Depends(get_operator_id),
):
    template = (
        db.query(Template)
        .filter(Template.kb_id == kb_id, Template.template_id == template_id)
        .one_or_none()
    )
    if template is None:
        return JSONResponse(
            status_code=404,
            content=error("NOT_FOUND", "Template not found", trace_id=get_trace_id()),
        )
    if body.expected_template_updated_at is not None:
        expected = body.expected_template_updated_at.astimezone(timezone.utc).replace(microsecond=0)
        current = template.updated_at.astimezone(timezone.utc).replace(microsecond=0)
        if expected != current:
            return JSONResponse(
                status_code=409,
                content=error(
                    "CONFLICT",
                    "Template has been modified by another operation",
                    trace_id=get_trace_id(),
                ),
            )

    chapter_rows = (
        db.query(TemplateChapter)
        .filter(TemplateChapter.template_id == template_id)
        .all()
    )
    rows_by_id = {row.template_chapter_id: row for row in chapter_rows}
    payload_by_id, validation_error = _validate_batch_tree(body.chapters, set(rows_by_id.keys()))
    if validation_error:
        return JSONResponse(
            status_code=422,
            content=error("INVALID_TREE", validation_error, trace_id=get_trace_id()),
        )

    for chapter_id, payload in payload_by_id.items():
        row = rows_by_id[chapter_id]
        row.parent_id = payload.parent_id
        row.title = payload.title.strip() or row.title
        row.level = payload.level
        row.sort_order = payload.sort_order
        row.chapter_taxonomy_id = payload.chapter_taxonomy_id
        row.product_category_ids = [str(item) for item in payload.product_category_ids]
        row.required = payload.required
        row.is_fixed_section = payload.is_fixed_section
        row.ignored = payload.ignored

    template.updated_at = datetime.now(timezone.utc)
    db.flush()
    audit = TemplateAuditLog(
        trace_id=get_trace_id() or UUID(int=0),
        kb_id=kb_id,
        template_id=template_id,
        template_library_id=template.template_library_id,
        import_id=template.source_import_id,
        operator_id=operator_id,
        action=TemplateAuditAction.chapter_update,
        payload_summary={
            "chapter_count": len(payload_by_id),
            "updated_at": template.updated_at.isoformat(),
        },
    )
    db.add(audit)
    db.commit()

    refreshed = (
        db.query(TemplateChapter)
        .filter(TemplateChapter.template_id == template_id)
        .order_by(TemplateChapter.level.asc(), TemplateChapter.sort_order.asc())
        .all()
    )
    roots = _build_nested_tree(refreshed)
    return success(
        {"template_id": str(template_id), "roots": roots, "audit_id": str(audit.audit_id)},
        trace_id=get_trace_id(),
    )
