import enum
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.chapter_draft import DraftOutcomeStatus
from src.models.generation_task import GenerationTaskStatus
from src.schemas.retrieval import OutlineNode

__all__ = [
    "CitationSourceType",
    "DraftOutcomeStatus",
    "DraftParagraph",
    "GenerationDraftCreateRequest",
    "GenerationDraftRegenerateRequest",
    "GenerationTaskStatus",
    "ManualAssetComplianceEntry",
    "ParagraphCitation",
    "ResolvedGenerationContext",
    "SourceCatalogEntry",
    "SuggestedChapterEnable",
    "UserChapterSelection",
]


class CitationSourceType(str, enum.Enum):
    tender_requirement = "tender_requirement"
    template_chapter = "template_chapter"
    ku = "ku"
    wiki = "wiki"
    manual_asset = "manual_asset"
    variable = "variable"


class SourceCatalogEntry(BaseModel):
    ref_id: str
    type: str
    object_id: str | None = None
    title: str
    excerpt: str


class SuggestedChapterEnable(BaseModel):
    template_chapter_id: UUID
    enabled: bool = True
    reason: str
    rule_id: UUID | None = None
    rule_type: str | None = None
    template_chapter_title: str | None = None
    risk_flags: list[dict] = Field(default_factory=list)


class ResolvedGenerationContext(BaseModel):
    layers: dict[str, list[str]]
    source_catalog: list[SourceCatalogEntry]
    conflict_pre_flags: list[dict] = Field(default_factory=list)
    suggested_chapter_enables: list[dict] = Field(default_factory=list)
    user_chapter_selections: list[dict] = Field(default_factory=list)


class ParagraphCitation(BaseModel):
    source_type: str
    source_id: str
    source_label: str
    excerpt: str
    ref_id: str | None = None


class DraftParagraph(BaseModel):
    paragraph_index: int
    text: str
    citations: list[ParagraphCitation] = Field(default_factory=list)


class UserChapterSelection(BaseModel):
    template_chapter_id: UUID
    enabled: bool = True
    source: str = "user_manual"


class ManualAssetComplianceEntry(BaseModel):
    manual_asset_id: UUID
    status: str
    message: str | None = None


class GenerationDraftCreateRequest(BaseModel):
    requirement_context_id: UUID
    suggestion_id: UUID
    target_outline_node: OutlineNode
    product_category_ids: list[UUID] = Field(default_factory=list)
    variable_values: dict[str, str] = Field(default_factory=dict)
    user_chapter_selections: list[UserChapterSelection] = Field(default_factory=list)
    manual_asset_compliance: list[ManualAssetComplianceEntry] = Field(default_factory=list)
    confirm_adoption: bool = False
    regenerate_from_draft_id: UUID | None = None


class GenerationDraftRegenerateRequest(BaseModel):
    variable_values: dict[str, str] | None = None
    user_chapter_selections: list[UserChapterSelection] | None = None
