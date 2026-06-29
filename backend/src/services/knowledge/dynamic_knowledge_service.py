from __future__ import annotations

import hashlib
import json
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.dynamic_knowledge_record import DynamicKnowledgeRecord
from src.services.knowledge.taxonomy_service import (
    validate_business_line_codes,
    validate_dynamic_type_code,
)


class DynamicKnowledgeNotFoundError(Exception):
    pass


def create_record(db: Session, *, kb_id: UUID, payload: dict) -> DynamicKnowledgeRecord:
    dynamic_type_code = validate_dynamic_type_code(
        db, str(payload.get("dynamic_type_code") or "").strip()
    )
    business_line_codes = validate_business_line_codes(db, payload.get("business_line_codes"))
    row = DynamicKnowledgeRecord(
        kb_id=kb_id,
        dynamic_type_code=dynamic_type_code,
        title=str(payload.get("title") or "").strip(),
        content=str(payload.get("content") or ""),
        structured_data=dict(payload.get("structured_data") or {}),
        business_line_codes=business_line_codes,
        source_type=str(payload.get("source_type") or "extracted"),
        source_doc_id=payload.get("source_doc_id"),
        source_chunk_id=payload.get("source_chunk_id"),
        issue_date=payload.get("issue_date"),
        expire_date=payload.get("expire_date"),
        status=str(payload.get("status") or "draft"),
        sync_status=str(payload.get("sync_status") or "pending"),
        content_hash=_compute_content_hash(payload),
    )
    db.add(row)
    db.flush()
    return row


def get_record(db: Session, *, kb_id: UUID, record_id: int) -> DynamicKnowledgeRecord | None:
    return (
        db.query(DynamicKnowledgeRecord)
        .filter(
            DynamicKnowledgeRecord.kb_id == kb_id,
            DynamicKnowledgeRecord.id == record_id,
        )
        .one_or_none()
    )


def list_records(db: Session, *, kb_id: UUID, filters: dict) -> tuple[list[DynamicKnowledgeRecord], int]:
    query = db.query(DynamicKnowledgeRecord).filter(DynamicKnowledgeRecord.kb_id == kb_id)
    dynamic_type_code = filters.get("dynamic_type_code")
    status = filters.get("status")
    expired_only = filters.get("expired_only")

    if dynamic_type_code:
        query = query.filter(DynamicKnowledgeRecord.dynamic_type_code == dynamic_type_code)
    if status:
        query = query.filter(DynamicKnowledgeRecord.status == status)
    if expired_only is True:
        query = query.filter(
            DynamicKnowledgeRecord.expire_date.is_not(None),
            DynamicKnowledgeRecord.expire_date < date.today(),
        )
    elif expired_only is False:
        query = query.filter(
            (DynamicKnowledgeRecord.expire_date.is_(None))
            | (DynamicKnowledgeRecord.expire_date >= date.today())
        )

    business_line_codes = filters.get("business_line_codes")
    rows = query.order_by(DynamicKnowledgeRecord.update_time.desc()).all()
    if business_line_codes:
        rows = [
            row
            for row in rows
            if _contains_any(row.business_line_codes or [], business_line_codes)
        ]
    total = len(rows)
    page = int(filters.get("page") or 1)
    page_size = int(filters.get("page_size") or 20)
    offset = (page - 1) * page_size
    return rows[offset : offset + page_size], total


def update_record(
    db: Session, *, kb_id: UUID, record_id: int, payload: dict
) -> DynamicKnowledgeRecord:
    row = get_record(db, kb_id=kb_id, record_id=record_id)
    if row is None:
        raise DynamicKnowledgeNotFoundError

    if "dynamic_type_code" in payload and payload["dynamic_type_code"] is not None:
        row.dynamic_type_code = validate_dynamic_type_code(
            db, str(payload.get("dynamic_type_code") or "").strip()
        )
    if "business_line_codes" in payload:
        row.business_line_codes = validate_business_line_codes(db, payload.get("business_line_codes"))

    if "title" in payload and payload["title"] is not None:
        row.title = str(payload["title"]).strip()
    if "content" in payload and payload["content"] is not None:
        row.content = str(payload["content"])
    if "structured_data" in payload and payload["structured_data"] is not None:
        row.structured_data = dict(payload["structured_data"])
    if "source_type" in payload and payload["source_type"] is not None:
        row.source_type = str(payload["source_type"])
    if "source_doc_id" in payload:
        row.source_doc_id = payload["source_doc_id"]
    if "source_chunk_id" in payload:
        row.source_chunk_id = payload["source_chunk_id"]
    if "issue_date" in payload:
        row.issue_date = payload["issue_date"]
    if "expire_date" in payload:
        row.expire_date = payload["expire_date"]
    if "status" in payload and payload["status"] is not None:
        row.status = str(payload["status"])
    if "sync_status" in payload and payload["sync_status"] is not None:
        row.sync_status = str(payload["sync_status"])

    row.content_hash = _compute_content_hash(
        {
            "title": row.title,
            "content": row.content,
            "structured_data": row.structured_data,
        }
    )
    db.flush()
    return row


def delete_record(db: Session, *, kb_id: UUID, record_id: int) -> None:
    row = get_record(db, kb_id=kb_id, record_id=record_id)
    if row is None:
        raise DynamicKnowledgeNotFoundError
    db.delete(row)
    db.flush()


def _compute_content_hash(payload: dict) -> str:
    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    structured_data = dict(payload.get("structured_data") or {})
    normalized = json.dumps(
        {"title": title, "content": content, "structured_data": structured_data},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _contains_any(target_values: list[str], filter_values: list[str] | None) -> bool:
    if not filter_values:
        return True
    target_set = {str(item).strip() for item in target_values if str(item).strip()}
    return any(value in target_set for value in filter_values)
