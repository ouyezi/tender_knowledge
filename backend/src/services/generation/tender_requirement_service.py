from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.tender_requirement_context import (
    TenderRequirementContext,
    TenderRequirementStatus,
)


class TenderRequirementValidationError(Exception):
    def __init__(self, message: str, *, code: str = "INVALID_OUTLINE"):
        self.code = code
        super().__init__(message)


def _validate_outline_nodes(outline_nodes: list[Any]) -> None:
    if not outline_nodes:
        raise TenderRequirementValidationError("outline_nodes cannot be empty")
    for node in outline_nodes:
        if not isinstance(node, dict) or not str(node.get("title", "")).strip():
            raise TenderRequirementValidationError("outline node missing title")


def serialize_tender_requirement(
    row: TenderRequirementContext,
    *,
    full: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "requirement_context_id": str(row.requirement_context_id),
        "title": row.title,
        "status": row.status.value,
        "created_at": row.created_at.isoformat(),
    }
    if not full:
        return payload

    payload.update(
        {
            "outline_structure": row.outline_structure,
            "outline_nodes": row.outline_nodes,
            "score_points": row.score_points,
            "rejection_clauses": row.rejection_clauses,
            "format_requirements": row.format_requirements,
            "qualification_requirements": row.qualification_requirements,
            "response_clauses": row.response_clauses,
            "source_note": row.source_note,
            "created_by": row.created_by,
            "updated_at": row.updated_at.isoformat(),
        }
    )
    return payload


class TenderRequirementService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        kb_id: UUID,
        title: str,
        outline_nodes: list[Any],
        operator_id: str | None = None,
        outline_structure: dict[str, Any] | None = None,
        score_points: list[Any] | None = None,
        rejection_clauses: list[Any] | None = None,
        format_requirements: list[Any] | None = None,
        qualification_requirements: list[Any] | None = None,
        response_clauses: list[Any] | None = None,
        source_note: str | None = None,
    ) -> TenderRequirementContext:
        _validate_outline_nodes(outline_nodes)
        row = TenderRequirementContext(
            kb_id=kb_id,
            title=title,
            outline_structure=outline_structure or {},
            outline_nodes=outline_nodes,
            score_points=score_points or [],
            rejection_clauses=rejection_clauses or [],
            format_requirements=format_requirements or [],
            qualification_requirements=qualification_requirements or [],
            response_clauses=response_clauses or [],
            source_note=source_note,
            created_by=operator_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def get(self, *, kb_id: UUID, requirement_context_id: UUID) -> TenderRequirementContext | None:
        return (
            self.db.query(TenderRequirementContext)
            .filter(
                TenderRequirementContext.kb_id == kb_id,
                TenderRequirementContext.requirement_context_id == requirement_context_id,
            )
            .one_or_none()
        )

    def list(
        self,
        *,
        kb_id: UUID,
        status: TenderRequirementStatus | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TenderRequirementContext], int]:
        query = self.db.query(TenderRequirementContext).filter(TenderRequirementContext.kb_id == kb_id)
        if status is not None:
            query = query.filter(TenderRequirementContext.status == status)
        if q:
            query = query.filter(TenderRequirementContext.title.ilike(f"%{q}%"))
        total = query.count()
        offset = max(page - 1, 0) * page_size
        rows = (
            query.order_by(TenderRequirementContext.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return rows, total

    def update(
        self,
        row: TenderRequirementContext,
        *,
        title: str | None = None,
        outline_structure: dict[str, Any] | None = None,
        outline_nodes: list[Any] | None = None,
        score_points: list[Any] | None = None,
        rejection_clauses: list[Any] | None = None,
        format_requirements: list[Any] | None = None,
        qualification_requirements: list[Any] | None = None,
        response_clauses: list[Any] | None = None,
        source_note: str | None = None,
        status: TenderRequirementStatus | None = None,
    ) -> TenderRequirementContext:
        if outline_nodes is not None:
            _validate_outline_nodes(outline_nodes)
            row.outline_nodes = outline_nodes
        if title is not None:
            row.title = title
        if outline_structure is not None:
            row.outline_structure = outline_structure
        if score_points is not None:
            row.score_points = score_points
        if rejection_clauses is not None:
            row.rejection_clauses = rejection_clauses
        if format_requirements is not None:
            row.format_requirements = format_requirements
        if qualification_requirements is not None:
            row.qualification_requirements = qualification_requirements
        if response_clauses is not None:
            row.response_clauses = response_clauses
        if source_note is not None:
            row.source_note = source_note
        if status is not None:
            row.status = status
        self.db.flush()
        return row

    def archive(self, row: TenderRequirementContext) -> TenderRequirementContext:
        row.status = TenderRequirementStatus.archived
        self.db.flush()
        return row
