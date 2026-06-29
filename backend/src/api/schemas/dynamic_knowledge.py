from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CreateDynamicKnowledgeRequest(BaseModel):
    dynamic_type_code: str
    title: str
    content: str = ""
    structured_data: dict[str, Any] = Field(default_factory=dict)
    business_line_codes: list[str] = Field(default_factory=lambda: ["general"])
    source_type: str = "extracted"
    source_doc_id: UUID | None = None
    source_chunk_id: int | None = None
    issue_date: date | None = None
    expire_date: date | None = None
    status: str = "draft"
    sync_status: str = "pending"


class UpdateDynamicKnowledgeRequest(BaseModel):
    dynamic_type_code: str | None = None
    title: str | None = None
    content: str | None = None
    structured_data: dict[str, Any] | None = None
    business_line_codes: list[str] | None = None
    source_type: str | None = None
    source_doc_id: UUID | None = None
    source_chunk_id: int | None = None
    issue_date: date | None = None
    expire_date: date | None = None
    status: str | None = None
    sync_status: str | None = None


class DynamicKnowledgeListFilters(BaseModel):
    dynamic_type_code: str | None = None
    status: str | None = None
    business_line_codes: list[str] | None = None
    expired_only: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
