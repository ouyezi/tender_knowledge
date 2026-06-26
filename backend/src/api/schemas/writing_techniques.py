from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateWritingTechniqueRequest(BaseModel):
    chunk_id: int = Field(ge=1)
    confirm_overwrite: bool = False


class CreateWritingTechniqueRequest(BaseModel):
    title: str
    applicable_scene: str | None = None
    writing_summary: str | None = None
    applicable_sections: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    usage_mode: str = "REFERENCE"
    recommended_outline: str | None = None
    writing_strategy: str | None = None
    must_include: str | None = None
    notes: str | None = None
    output_requirement: str | None = None
    checklist: str | None = None
    confidence: int = 0
    source_chunk_id: int | None = None


class UpdateWritingTechniqueRequest(CreateWritingTechniqueRequest):
    pass


class BindSourceRequest(BaseModel):
    chunk_id: int = Field(ge=1)


class WritingTechniqueListFilters(BaseModel):
    keyword: str | None = None
    tags: list[str] | None = None
    applicable_sections: list[str] | None = None
    usage_mode: str | None = None
    status: str | None = None
    confidence_min: int | None = None
    confidence_max: int | None = None
    source_invalid: bool | None = None
    has_source: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    def to_service_kwargs(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "tags": self.tags,
            "applicable_sections": self.applicable_sections,
            "usage_mode": self.usage_mode,
            "status": self.status,
            "confidence_min": self.confidence_min,
            "confidence_max": self.confidence_max,
            "source_invalid": self.source_invalid,
            "has_source": self.has_source,
            "page": self.page,
            "page_size": self.page_size,
        }
