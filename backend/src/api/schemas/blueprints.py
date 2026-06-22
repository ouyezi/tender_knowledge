from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BlueprintNodeInput(BaseModel):
    node_title: str
    node_level: int = 1
    node_order: int | None = None
    purpose: str | None = None
    writing_goal: str | None = None
    writing_hint: str | None = None
    content_description: str | None = None
    tender_response_hint: str | None = None
    importance_level: str = "optional"
    content_type: str | None = None
    keyword_hint: list[str] = Field(default_factory=list)
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
    related_regulations: list[str] = Field(default_factory=list)
    overall_strategy: str | None = None
    common_mistakes: str | None = None
    template_style: str | None = None
    usual_page_range: str | None = None
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
