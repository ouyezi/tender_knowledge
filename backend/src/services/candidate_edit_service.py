from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.candidate_confirm_audit_log import CandidateConfirmAuditAction
from src.models.candidate_knowledge import CandidateKnowledgeType
from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.product_category import CategoryStatus, ProductCategory
from src.services import candidate_audit_service
from src.services.candidate_adapter import (
    assert_editable_document,
    assert_editable_stub,
    get_document_row,
    get_stub_row,
    load_candidate,
)


class InvalidTaxonomyError(Exception):
    pass


class InvalidProductCategoryError(Exception):
    pass


def _validate_taxonomy(db: Session, *, kb_id: UUID, taxonomy_id: UUID | None) -> None:
    if taxonomy_id is None:
        return
    taxonomy = (
        db.query(ChapterTaxonomy)
        .filter(ChapterTaxonomy.kb_id == kb_id)
        .filter(ChapterTaxonomy.taxonomy_id == taxonomy_id)
        .first()
    )
    if taxonomy is None or taxonomy.status != CategoryStatus.active:
        raise InvalidTaxonomyError


def _validate_product_categories(
    db: Session, *, kb_id: UUID, category_ids: list[UUID]
) -> None:
    for category_id in category_ids:
        category = (
            db.query(ProductCategory)
            .filter(ProductCategory.kb_id == kb_id)
            .filter(ProductCategory.category_id == category_id)
            .first()
        )
        if category is None or category.status != CategoryStatus.active:
            raise InvalidProductCategoryError


def _collect_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {key: after[key] for key in after if before.get(key) != after.get(key)}


def edit_candidate(
    db: Session,
    *,
    kb_id: UUID,
    candidate_id: str,
    payload: dict[str, Any],
    operator_id: str,
    trace_id: UUID,
) -> dict[str, Any]:
    view = load_candidate(db, kb_id=kb_id, candidate_id=candidate_id)

    if view.channel == "document":
        row = get_document_row(db, kb_id=kb_id, candidate_id=candidate_id)
        assert_editable_document(row.status)
        before = {
            "title": row.title,
            "summary": row.summary,
            "content": row.content,
            "suggested_knowledge_type": row.suggested_knowledge_type,
            "suggested_chapter_taxonomy_id": row.suggested_chapter_taxonomy_id,
            "suggested_product_category_ids": row.suggested_product_category_ids,
            "candidate_type": row.candidate_type.value,
        }

        if "suggested_chapter_taxonomy_id" in payload:
            taxonomy_id = payload["suggested_chapter_taxonomy_id"]
            _validate_taxonomy(db, kb_id=kb_id, taxonomy_id=taxonomy_id)
            row.suggested_chapter_taxonomy_id = taxonomy_id

        if "suggested_product_category_ids" in payload:
            category_ids = payload["suggested_product_category_ids"] or []
            _validate_product_categories(db, kb_id=kb_id, category_ids=category_ids)
            row.suggested_product_category_ids = [str(item) for item in category_ids]

        if "title" in payload and payload["title"] is not None:
            row.title = payload["title"]
        if "summary" in payload:
            row.summary = payload["summary"]
        if "content" in payload:
            row.content = payload["content"]
        if "suggested_knowledge_type" in payload:
            row.suggested_knowledge_type = payload["suggested_knowledge_type"]
        if "candidate_type" in payload and payload["candidate_type"] is not None:
            row.candidate_type = CandidateKnowledgeType(payload["candidate_type"])

        after = {
            "title": row.title,
            "summary": row.summary,
            "content": row.content,
            "suggested_knowledge_type": row.suggested_knowledge_type,
            "suggested_chapter_taxonomy_id": row.suggested_chapter_taxonomy_id,
            "suggested_product_category_ids": row.suggested_product_category_ids,
            "candidate_type": row.candidate_type.value,
        }
        status_label = "pending"
    else:
        row = get_stub_row(db, kb_id=kb_id, candidate_id=candidate_id)
        assert_editable_stub(row.status)
        before = {
            "title": row.title,
            "summary": row.summary,
            "content": row.content_preview,
            "suggested_knowledge_type": row.suggested_knowledge_type,
            "suggested_chapter_taxonomy_id": row.chapter_taxonomy_id,
            "suggested_product_category_ids": row.product_category_ids,
            "candidate_type": row.candidate_type.value,
        }

        if "suggested_chapter_taxonomy_id" in payload:
            taxonomy_id = payload["suggested_chapter_taxonomy_id"]
            _validate_taxonomy(db, kb_id=kb_id, taxonomy_id=taxonomy_id)
            row.chapter_taxonomy_id = taxonomy_id

        if "suggested_product_category_ids" in payload:
            category_ids = payload["suggested_product_category_ids"] or []
            _validate_product_categories(db, kb_id=kb_id, category_ids=category_ids)
            row.product_category_ids = [str(item) for item in category_ids]

        if "title" in payload and payload["title"] is not None:
            row.title = payload["title"]
        if "summary" in payload:
            row.summary = payload["summary"]
        if "content" in payload:
            row.content_preview = payload["content"]
        if "suggested_knowledge_type" in payload:
            row.suggested_knowledge_type = payload["suggested_knowledge_type"]
        if "candidate_type" in payload and payload["candidate_type"] is not None:
            row.candidate_type = CandidateKnowledgeType(payload["candidate_type"])

        after = {
            "title": row.title,
            "summary": row.summary,
            "content": row.content_preview,
            "suggested_knowledge_type": row.suggested_knowledge_type,
            "suggested_chapter_taxonomy_id": row.chapter_taxonomy_id,
            "suggested_product_category_ids": row.product_category_ids,
            "candidate_type": row.candidate_type.value,
        }
        status_label = "pending"

    row.updated_by = operator_id
    row.updated_at = datetime.now(timezone.utc)
    changes = _collect_changes(before, after)

    candidate_audit_service.write_audit(
        db,
        kb_id=kb_id,
        candidate_id=view.candidate_id,
        action=CandidateConfirmAuditAction.edit,
        operator_id=operator_id,
        trace_id=trace_id,
        detail={"changes": changes},
    )
    db.commit()
    db.refresh(row)

    return {
        "candidate_id": view.candidate_id,
        "status": status_label,
        "updated_at": row.updated_at.isoformat(),
    }
