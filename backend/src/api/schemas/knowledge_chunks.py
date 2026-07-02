from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PrefillRequest(BaseModel):
    doc_id: UUID
    primary_node_id: UUID
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntryTreeRefineRequest(BaseModel):
    instruction: str | None = None


class CreateKnowledgeChunkRequest(BaseModel):
    doc_id: UUID
    primary_node_id: UUID
    title: str
    content: str
    summary: str | None = None
    knowledge_type: str = "fact"
    content_type: str = "text"
    file_name: str | None = None
    catalog_path: list[dict[str, Any]] = Field(default_factory=list)
    block_type_code: str = "product_solution"
    application_type_code: str = "preferred_reference"
    business_line_codes: list[str] = Field(default_factory=lambda: ["general"])
    tags: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    qualification_info: str | None = None
    expire_date: date | None = None
    status: str = "draft"
    is_template: bool = False
    template_type: str | None = None
    security_level: str = "internal"
    owner: str | None = None
    review_status: str = "approved"
    force: bool = False


class IndexKnowledgeChunkRequest(BaseModel):
    force: bool = False


class MarkChunksIndexFailedRequest(BaseModel):
    chunk_ids: list[int] = Field(..., min_length=1, max_length=200)


class ParseChunkSearchQueryRequest(BaseModel):
    query: str


class ChunkSearchRequest(BaseModel):
    semantic_query: str = ""
    keyword: str = ""
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    title_vector_weight: float = 0.25
    summary_vector_weight: float = 0.35
    content_vector_weight: float = 0.4
    top_k: int = Field(default=10, ge=1, le=50)


class KnowledgeChunkListFilters(BaseModel):
    block_type_code: str | None = None
    application_type_code: str | None = None
    business_line_codes: list[str] | None = None
    knowledge_type: str | None = None
    status: str | None = None
    regions: list[str] | None = None
    tags: list[str] | None = None
    security_level: str | None = None
    is_template: bool | None = None
    review_status: str | None = None
    expire_date_from: date | None = None
    expire_date_to: date | None = None
    expired_only: bool | None = None
    keyword: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
