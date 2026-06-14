from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.candidate_confirm_audit_log import CandidateConfirmAuditAction
from src.models.candidate_knowledge import (
    CandidateKnowledge,
    CandidateKnowledgeStatus,
    CandidateKnowledgeType,
)
from src.models.candidate_knowledge_stub import CandidateKnowledgeStubStatus
from src.services import candidate_audit_service
from src.services.candidate_adapter import (
    CandidateNotFoundError,
    assert_editable_document,
    assert_editable_stub,
    format_candidate_id,
    get_document_row,
    get_stub_row,
    load_candidate,
)


class MergeInvalidTargetError(Exception):
    pass


class MergeSourceNotPendingError(Exception):
    def __init__(self, candidate_id: str, status: str) -> None:
        self.candidate_id = candidate_id
        self.status = status
        super().__init__(f"source candidate {candidate_id} status={status} is not pending")


class SplitNotSupportedError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _assert_pending_for_merge_target(db: Session, *, kb_id: UUID, candidate_id: str) -> None:
    view = load_candidate(db, kb_id=kb_id, candidate_id=candidate_id)
    if view.channel == "document":
        row = get_document_row(db, kb_id=kb_id, candidate_id=candidate_id)
        try:
            assert_editable_document(row.status)
        except Exception as exc:
            raise MergeInvalidTargetError from exc
        return

    row = get_stub_row(db, kb_id=kb_id, candidate_id=candidate_id)
    try:
        assert_editable_stub(row.status)
    except Exception as exc:
        raise MergeInvalidTargetError from exc


def _assert_pending_source_or_raise(db: Session, *, kb_id: UUID, candidate_id: str) -> None:
    view = load_candidate(db, kb_id=kb_id, candidate_id=candidate_id)
    if view.channel == "document":
        row = get_document_row(db, kb_id=kb_id, candidate_id=candidate_id)
        try:
            assert_editable_document(row.status)
        except Exception as exc:
            raise MergeSourceNotPendingError(candidate_id, row.status.value) from exc
        return

    row = get_stub_row(db, kb_id=kb_id, candidate_id=candidate_id)
    try:
        assert_editable_stub(row.status)
    except Exception as exc:
        raise MergeSourceNotPendingError(candidate_id, row.status.value) from exc


def merge_candidates(
    db: Session,
    *,
    kb_id: UUID,
    target_candidate_id: str,
    source_candidate_ids: list[str],
    payload: dict[str, Any],
    operator_id: str,
    trace_id: UUID,
) -> dict[str, Any]:
    unique_sources = list(dict.fromkeys(source_candidate_ids))
    if not unique_sources or target_candidate_id in unique_sources:
        raise MergeInvalidTargetError

    _assert_pending_for_merge_target(db, kb_id=kb_id, candidate_id=target_candidate_id)
    for source_id in unique_sources:
        _assert_pending_source_or_raise(db, kb_id=kb_id, candidate_id=source_id)

    target_view = load_candidate(db, kb_id=kb_id, candidate_id=target_candidate_id)
    now = _now()

    if target_view.channel == "document":
        target_row = get_document_row(db, kb_id=kb_id, candidate_id=target_candidate_id)
        if "title" in payload and payload["title"] is not None:
            target_row.title = payload["title"]
        if "summary" in payload:
            target_row.summary = payload["summary"]
        if "content" in payload:
            target_row.content = payload["content"]
    else:
        target_row = get_stub_row(db, kb_id=kb_id, candidate_id=target_candidate_id)
        if "title" in payload and payload["title"] is not None:
            target_row.title = payload["title"]
        if "summary" in payload:
            target_row.summary = payload["summary"]
        if "content" in payload:
            target_row.content_preview = payload["content"]

    target_row.review_comment = payload.get("review_comment")
    target_row.updated_by = operator_id
    target_row.updated_at = now
    target_row.lineage = {
        **(target_row.lineage or {}),
        "merge": {
            "source_candidate_ids": unique_sources,
            "trace_id": str(trace_id),
        },
    }

    target_raw_id = target_view.raw_id
    for source_id in unique_sources:
        source_view = load_candidate(db, kb_id=kb_id, candidate_id=source_id)
        if source_view.channel == "document":
            source_row = get_document_row(db, kb_id=kb_id, candidate_id=source_id)
            source_row.status = CandidateKnowledgeStatus.merged
            source_row.merged_into_id = target_raw_id
        else:
            source_row = get_stub_row(db, kb_id=kb_id, candidate_id=source_id)
            source_row.status = CandidateKnowledgeStubStatus.merged
            source_row.merged_into_id = target_raw_id

        source_row.updated_by = operator_id
        source_row.updated_at = now
        source_row.lineage = {
            **(source_row.lineage or {}),
            "merge": {
                "target_candidate_id": target_candidate_id,
                "trace_id": str(trace_id),
            },
        }

    candidate_audit_service.write_audit(
        db,
        kb_id=kb_id,
        candidate_id=target_candidate_id,
        action=CandidateConfirmAuditAction.merge,
        operator_id=operator_id,
        trace_id=trace_id,
        detail={
            "target_candidate_id": target_candidate_id,
            "source_candidate_ids": unique_sources,
            "review_comment": payload.get("review_comment"),
        },
    )
    db.commit()

    return {
        "target_candidate_id": target_candidate_id,
        "merged_count": len(unique_sources),
        "status": "pending",
        "trace_id": str(trace_id),
    }


def split_candidate(
    db: Session,
    *,
    kb_id: UUID,
    candidate_id: str,
    splits: list[dict[str, Any]],
    review_comment: str | None,
    operator_id: str,
    trace_id: UUID,
) -> dict[str, Any]:
    view = load_candidate(db, kb_id=kb_id, candidate_id=candidate_id)
    if view.channel != "document":
        raise SplitNotSupportedError("split only supports document candidates")

    source_row = get_document_row(db, kb_id=kb_id, candidate_id=candidate_id)
    assert_editable_document(source_row.status)
    if len(splits) < 2:
        raise ValueError("splits must include at least 2 items")

    now = _now()
    new_candidates: list[CandidateKnowledge] = []
    new_candidate_ids: list[str] = []
    for split in splits:
        candidate_type = CandidateKnowledgeType(split.get("candidate_type", source_row.candidate_type.value))
        row = CandidateKnowledge(
            kb_id=kb_id,
            import_id=source_row.import_id,
            source_doc_id=source_row.source_doc_id,
            source_node_id=source_row.source_node_id,
            candidate_type=candidate_type,
            title=split.get("title") or source_row.title,
            content=split.get("content"),
            summary=split.get("summary"),
            suggested_knowledge_type=split.get("suggested_knowledge_type"),
            suggested_chapter_taxonomy_id=split.get("suggested_chapter_taxonomy_id"),
            suggested_product_category_ids=[
                str(item) for item in (split.get("suggested_product_category_ids") or [])
            ],
            confidence_score=source_row.confidence_score,
            suggestion_source=source_row.suggestion_source,
            status=CandidateKnowledgeStatus.pending,
            parse_task_id=source_row.parse_task_id,
            split_from_id=source_row.candidate_id,
            lineage={
                "split": {
                    "source_candidate_id": candidate_id,
                    "trace_id": str(trace_id),
                }
            },
            updated_by=operator_id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        new_candidates.append(row)

    db.flush()
    for row in new_candidates:
        new_candidate_ids.append(format_candidate_id("document", row.candidate_id))

    source_row.status = CandidateKnowledgeStatus.merged
    source_row.review_comment = review_comment
    source_row.updated_by = operator_id
    source_row.updated_at = now
    source_row.lineage = {
        **(source_row.lineage or {}),
        "split": {
            "new_candidate_ids": new_candidate_ids,
            "trace_id": str(trace_id),
        },
    }

    candidate_audit_service.write_audit(
        db,
        kb_id=kb_id,
        candidate_id=candidate_id,
        action=CandidateConfirmAuditAction.split,
        operator_id=operator_id,
        trace_id=trace_id,
        detail={
            "source_candidate_id": candidate_id,
            "new_candidate_ids": new_candidate_ids,
            "review_comment": review_comment,
        },
    )
    db.commit()

    return {
        "source_candidate_id": candidate_id,
        "new_candidate_ids": new_candidate_ids,
        "source_status": "merged",
        "trace_id": str(trace_id),
    }
