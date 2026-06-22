from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BlueprintNodeInput(BaseModel):
    node_title: str
    node_level: int = 1
    node_order: int | None = None
    content_description: str | None = None
    tender_response_hint: str | None = None
    importance_level: str = "optional"
    children: list["BlueprintNodeInput"] = Field(default_factory=list)


BlueprintNodeInput.model_rebuild()


class GenerateBlueprintRequest(BaseModel):
    doc_id: UUID
    node_id: UUID


class SaveBlueprintRequest(BaseModel):
    name: str
    description: str | None = None
    source_doc_id: UUID
    source_node_id: UUID
    source_chapter_title: str | None = None
    product_tags: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    scenario_tags: list[str] = Field(default_factory=list)
    applicable_project_type: list[str] = Field(default_factory=list)
    suggested_structure_md: str | None = None
    status: str = "active"
    version: int | None = None
    nodes: list[BlueprintNodeInput] = Field(default_factory=list)


class BlueprintListFilters(BaseModel):
    keyword: str | None = None
    product_tags: list[str] | None = None
    industry_tags: list[str] | None = None
    scenario_tags: list[str] | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    def to_service_kwargs(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "product_tags": self.product_tags,
            "industry_tags": self.industry_tags,
            "scenario_tags": self.scenario_tags,
            "page": self.page,
            "page_size": self.page_size,
        }


class SuggestOutlineRequest(BaseModel):
    blueprint_ids: list[UUID] = Field(min_length=1)
    requirement_description: str = Field(min_length=1)


class SuggestOutlineNode(BaseModel):
    title: str
    content_suggestion: str
    importance: str
    split_reason: str | None = None
    no_split_reason: str | None = None
    children: list["SuggestOutlineNode"] = Field(default_factory=list)


SuggestOutlineNode.model_rebuild()


class SuggestOutlineResponse(BaseModel):
    outline_title: str
    summary: str
    nodes: list[SuggestOutlineNode] = Field(default_factory=list)
