from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.candidate_knowledge import (
    CandidateKnowledge,
    CandidateKnowledgeStatus,
    CandidateKnowledgeType,
)
from src.models.candidate_knowledge_stub import (
    CandidateKnowledgeStub,
    CandidateKnowledgeStubStatus,
)


class CandidateNotEditableError(Exception):
    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(f"candidate not editable in status={status}")


class CandidateNotFoundError(Exception):
    pass


@dataclass
class CandidateView:
    candidate_id: str
    channel: str
    raw_id: UUID
    kb_id: UUID
    title: str
    content: str | None
    summary: str | None
    status: str
    candidate_type: str
    suggested_knowledge_type: str | None
    suggested_chapter_taxonomy_id: UUID | None
    suggested_product_category_ids: list[Any]
    confidence_score: float | None
    source_trace: dict[str, Any]
    confirmed_object_type: str | None = None
    confirmed_object_id: UUID | None = None


def parse_candidate_id(candidate_id: str) -> tuple[str, UUID]:
    if candidate_id.startswith("doc_"):
        return "document", UUID(candidate_id.removeprefix("doc_"))
    if candidate_id.startswith("tpl_"):
        return "template", UUID(candidate_id.removeprefix("tpl_"))
    raise ValueError("invalid candidate_id")


def format_candidate_id(channel: str, raw_id: UUID) -> str:
    prefix = "doc_" if channel == "document" else "tpl_"
    return f"{prefix}{raw_id}"


def assert_editable_document(status: CandidateKnowledgeStatus) -> None:
    if status != CandidateKnowledgeStatus.pending:
        raise CandidateNotEditableError(status.value)


def assert_editable_stub(status: CandidateKnowledgeStubStatus) -> None:
    if status != CandidateKnowledgeStubStatus.pending_confirm:
        raise CandidateNotEditableError(status.value)


def _document_status_label(status: CandidateKnowledgeStatus) -> str:
    return "pending" if status == CandidateKnowledgeStatus.pending else status.value


def _stub_status_label(status: CandidateKnowledgeStubStatus) -> str:
    if status == CandidateKnowledgeStubStatus.pending_confirm:
        return "pending"
    return status.value


def load_candidate(db: Session, *, kb_id: UUID, candidate_id: str) -> CandidateView:
    channel, raw_id = parse_candidate_id(candidate_id)
    if channel == "document":
        row = (
            db.query(CandidateKnowledge)
            .filter(CandidateKnowledge.kb_id == kb_id)
            .filter(CandidateKnowledge.candidate_id == raw_id)
            .first()
        )
        if row is None:
            raise CandidateNotFoundError
        return CandidateView(
            candidate_id=format_candidate_id("document", row.candidate_id),
            channel="document",
            raw_id=row.candidate_id,
            kb_id=row.kb_id,
            title=row.title,
            content=row.content,
            summary=row.summary,
            status=_document_status_label(row.status),
            candidate_type=row.candidate_type.value,
            suggested_knowledge_type=row.suggested_knowledge_type,
            suggested_chapter_taxonomy_id=row.suggested_chapter_taxonomy_id,
            suggested_product_category_ids=row.suggested_product_category_ids,
            confidence_score=row.confidence_score,
            source_trace={
                "import_id": str(row.import_id),
                "source_doc_id": str(row.source_doc_id),
                "source_node_id": str(row.source_node_id),
            },
            confirmed_object_type=row.confirmed_object_type,
            confirmed_object_id=row.confirmed_object_id,
        )

    row = (
        db.query(CandidateKnowledgeStub)
        .filter(CandidateKnowledgeStub.kb_id == kb_id)
        .filter(CandidateKnowledgeStub.stub_id == raw_id)
        .first()
    )
    if row is None:
        raise CandidateNotFoundError
    return CandidateView(
        candidate_id=format_candidate_id("template", row.stub_id),
        channel="template",
        raw_id=row.stub_id,
        kb_id=row.kb_id,
        title=row.title,
        content=row.content_preview,
        summary=row.summary,
        status=_stub_status_label(row.status),
        candidate_type=row.candidate_type.value,
        suggested_knowledge_type=row.suggested_knowledge_type,
        suggested_chapter_taxonomy_id=row.chapter_taxonomy_id,
        suggested_product_category_ids=row.product_category_ids,
        confidence_score=row.classification_confidence,
        source_trace={
            "import_id": str(row.import_id),
            "template_id": str(row.template_id),
            "template_chapter_id": str(row.template_chapter_id) if row.template_chapter_id else None,
            "material_id": str(row.material_id) if row.material_id else None,
        },
        confirmed_object_type=row.confirmed_object_type,
        confirmed_object_id=row.confirmed_object_id,
    )


def get_document_row(db: Session, *, kb_id: UUID, candidate_id: str) -> CandidateKnowledge:
    channel, raw_id = parse_candidate_id(candidate_id)
    if channel != "document":
        raise CandidateNotFoundError
    row = (
        db.query(CandidateKnowledge)
        .filter(CandidateKnowledge.kb_id == kb_id)
        .filter(CandidateKnowledge.candidate_id == raw_id)
        .first()
    )
    if row is None:
        raise CandidateNotFoundError
    return row


def get_stub_row(db: Session, *, kb_id: UUID, candidate_id: str) -> CandidateKnowledgeStub:
    channel, raw_id = parse_candidate_id(candidate_id)
    if channel != "template":
        raise CandidateNotFoundError
    row = (
        db.query(CandidateKnowledgeStub)
        .filter(CandidateKnowledgeStub.kb_id == kb_id)
        .filter(CandidateKnowledgeStub.stub_id == raw_id)
        .first()
    )
    if row is None:
        raise CandidateNotFoundError
    return row
