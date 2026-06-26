from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import String, and_, cast, or_
from sqlalchemy.orm import Session

from src.models.knowledge_chunk import KnowledgeChunk
from src.models.writing_technique import TechniqueStatus, UsageMode, WritingTechnique
from src.services.knowledge.writing_technique_field_utils import (
    APPLICABLE_SCENE_MAX,
    TITLE_MAX,
    WRITING_STRATEGY_MAX,
    WRITING_SUMMARY_MAX,
    clamp_confidence,
    coerce_usage_mode,
    truncate_technique_field,
)


class TechniqueNotFoundError(Exception):
    pass


class TechniqueConflictError(Exception):
    pass


class TechniqueChunkBoundError(Exception):
    pass


class TechniqueValidationError(Exception):
    pass


def create_technique(db: Session, *, kb_id: UUID, payload: dict[str, Any]) -> WritingTechnique:
    source_chunk_id = _as_optional_int(payload.get("source_chunk_id"))
    if source_chunk_id is not None:
        existing = get_technique_by_source(db, kb_id=kb_id, chunk_id=source_chunk_id)
        if existing is not None:
            raise TechniqueConflictError("source chunk already has a technique")

    row = WritingTechnique(kb_id=kb_id)
    _apply_payload_fields(row, payload)
    row.source_chunk_id = source_chunk_id
    row.source_invalid = bool(payload.get("source_invalid", False))

    db.add(row)
    db.flush()
    return row


def update_technique(
    db: Session,
    *,
    kb_id: UUID,
    technique_id: UUID,
    payload: dict[str, Any],
) -> WritingTechnique:
    row = _get_technique_row(db, kb_id=kb_id, technique_id=technique_id)

    if "source_chunk_id" in payload:
        source_chunk_id = _as_optional_int(payload.get("source_chunk_id"))
        if source_chunk_id is None:
            row.source_chunk_id = None
        else:
            existing = get_technique_by_source(db, kb_id=kb_id, chunk_id=source_chunk_id)
            if existing is not None and existing.technique_id != row.technique_id:
                raise TechniqueConflictError("source chunk already has a technique")
            row.source_chunk_id = source_chunk_id
            row.source_invalid = False

    _apply_payload_fields(row, payload, partial=True)
    if "source_invalid" in payload:
        row.source_invalid = bool(payload.get("source_invalid"))

    row.version = int(row.version) + 1
    db.flush()
    return row


def get_technique_detail(db: Session, *, kb_id: UUID, technique_id: UUID) -> WritingTechnique:
    return _get_technique_row(db, kb_id=kb_id, technique_id=technique_id)


def get_technique_by_source(
    db: Session, *, kb_id: UUID, chunk_id: int
) -> WritingTechnique | None:
    return (
        db.query(WritingTechnique)
        .filter(
            WritingTechnique.kb_id == kb_id,
            WritingTechnique.source_chunk_id == int(chunk_id),
        )
        .one_or_none()
    )


def list_techniques(
    db: Session,
    *,
    kb_id: UUID,
    filters: dict[str, Any] | None = None,
) -> tuple[list[WritingTechnique], int]:
    params = filters or {}
    query = db.query(WritingTechnique).filter(WritingTechnique.kb_id == kb_id)

    keyword = str(params.get("keyword") or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                WritingTechnique.title.ilike(pattern),
                WritingTechnique.writing_summary.ilike(pattern),
            )
        )

    query = _apply_json_array_filter(query, WritingTechnique.tags, params.get("tags"))
    query = _apply_json_array_filter(
        query, WritingTechnique.applicable_sections, params.get("applicable_sections")
    )

    usage_mode = params.get("usage_mode")
    if usage_mode is not None and str(usage_mode).strip():
        query = query.filter(WritingTechnique.usage_mode == UsageMode(coerce_usage_mode(usage_mode)))

    status = params.get("status")
    if status is not None and str(status).strip():
        try:
            normalized_status = TechniqueStatus(str(status).strip())
        except ValueError as exc:
            raise TechniqueValidationError("invalid status filter") from exc
        query = query.filter(WritingTechnique.status == normalized_status)

    if params.get("confidence_min") is not None:
        query = query.filter(WritingTechnique.confidence >= int(params.get("confidence_min")))
    if params.get("confidence_max") is not None:
        query = query.filter(WritingTechnique.confidence <= int(params.get("confidence_max")))

    if params.get("source_invalid") is not None:
        query = query.filter(WritingTechnique.source_invalid.is_(bool(params.get("source_invalid"))))

    if params.get("has_source") is not None:
        if bool(params.get("has_source")):
            query = query.filter(WritingTechnique.source_chunk_id.is_not(None))
        else:
            query = query.filter(WritingTechnique.source_chunk_id.is_(None))

    total = query.count()
    page = max(int(params.get("page") or 1), 1)
    page_size = max(int(params.get("page_size") or 20), 1)
    rows = (
        query.order_by(WritingTechnique.updated_at.desc(), WritingTechnique.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total


def delete_technique(db: Session, *, kb_id: UUID, technique_id: UUID) -> None:
    row = _get_technique_row(db, kb_id=kb_id, technique_id=technique_id)
    db.delete(row)
    db.flush()


def bind_source_chunk(
    db: Session,
    *,
    kb_id: UUID,
    technique_id: UUID,
    chunk_id: int,
) -> WritingTechnique:
    row = _get_technique_row(db, kb_id=kb_id, technique_id=technique_id)
    _ensure_chunk_exists(db, kb_id=kb_id, chunk_id=chunk_id)

    existing = get_technique_by_source(db, kb_id=kb_id, chunk_id=chunk_id)
    if existing is not None and existing.technique_id != row.technique_id:
        raise TechniqueChunkBoundError("source chunk already bound")

    row.source_chunk_id = int(chunk_id)
    row.source_invalid = False
    db.flush()
    return row


def publish_technique(
    db: Session, *, kb_id: UUID, technique_id: UUID
) -> WritingTechnique:
    row = _get_technique_row(db, kb_id=kb_id, technique_id=technique_id)
    row.status = TechniqueStatus.published
    row.version = int(row.version) + 1
    db.flush()
    return row


def invalidate_techniques_by_chunk_ids(
    db: Session,
    *,
    kb_id: UUID,
    chunk_ids: list[int],
) -> int:
    normalized_ids = [int(chunk_id) for chunk_id in chunk_ids if chunk_id is not None]
    if not normalized_ids:
        return 0

    now = datetime.now(timezone.utc)
    count = (
        db.query(WritingTechnique)
        .filter(
            WritingTechnique.kb_id == kb_id,
            WritingTechnique.source_chunk_id.in_(normalized_ids),
        )
        .update(
            {
                WritingTechnique.source_chunk_id: None,
                WritingTechnique.source_invalid: True,
                WritingTechnique.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    db.flush()
    return int(count)


def apply_llm_payload(row: WritingTechnique, payload: dict[str, Any]) -> None:
    _apply_payload_fields(row, payload, partial=True)


def _get_technique_row(
    db: Session, *, kb_id: UUID, technique_id: UUID
) -> WritingTechnique:
    row = (
        db.query(WritingTechnique)
        .filter(
            WritingTechnique.kb_id == kb_id,
            WritingTechnique.technique_id == technique_id,
        )
        .one_or_none()
    )
    if row is None:
        raise TechniqueNotFoundError
    return row


def _apply_payload_fields(
    row: WritingTechnique,
    payload: dict[str, Any],
    *,
    partial: bool = False,
) -> None:
    if not partial or "title" in payload:
        normalized_title = truncate_technique_field(payload.get("title"), max_len=TITLE_MAX)
        if not normalized_title:
            raise TechniqueValidationError("title is required")
        row.title = normalized_title

    if "applicable_scene" in payload or not partial:
        row.applicable_scene = truncate_technique_field(
            payload.get("applicable_scene"), max_len=APPLICABLE_SCENE_MAX
        )
    if "writing_summary" in payload or not partial:
        row.writing_summary = truncate_technique_field(
            payload.get("writing_summary"), max_len=WRITING_SUMMARY_MAX
        )
    if "applicable_sections" in payload or not partial:
        row.applicable_sections = _as_str_list(payload.get("applicable_sections"))
    if "tags" in payload or not partial:
        row.tags = _as_str_list(payload.get("tags"))
    if "usage_mode" in payload or not partial:
        row.usage_mode = UsageMode(coerce_usage_mode(payload.get("usage_mode")))
    if "recommended_outline" in payload or not partial:
        row.recommended_outline = _normalize_text(payload.get("recommended_outline"))
    if "writing_strategy" in payload or not partial:
        row.writing_strategy = truncate_technique_field(
            payload.get("writing_strategy"), max_len=WRITING_STRATEGY_MAX
        )
    if "must_include" in payload or not partial:
        row.must_include = _normalize_text(payload.get("must_include"))
    if "notes" in payload or not partial:
        row.notes = _normalize_text(payload.get("notes"))
    if "output_requirement" in payload or not partial:
        row.output_requirement = _normalize_text(payload.get("output_requirement"))
    if "checklist" in payload or not partial:
        row.checklist = _normalize_text(payload.get("checklist"))
    if "confidence" in payload or not partial:
        row.confidence = clamp_confidence(payload.get("confidence"))
    if "status" in payload and payload.get("status") is not None:
        row.status = TechniqueStatus(str(payload.get("status")).strip())
    if "version" in payload and payload.get("version") is not None:
        row.version = max(int(payload.get("version")), 1)


def _apply_json_array_filter(query, column, values: Any):
    normalized = _as_str_list(values)
    if not normalized:
        return query
    conditions = [cast(column, String).ilike(f'%"{item}"%') for item in normalized]
    return query.filter(and_(*conditions))


def _ensure_chunk_exists(db: Session, *, kb_id: UUID, chunk_id: int) -> None:
    exists = (
        db.query(KnowledgeChunk.id)
        .filter(
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.id == int(chunk_id),
            KnowledgeChunk.is_latest.is_(True),
        )
        .scalar()
    )
    if exists is None:
        raise TechniqueValidationError("chunk not found")


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TechniqueValidationError("array field must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
