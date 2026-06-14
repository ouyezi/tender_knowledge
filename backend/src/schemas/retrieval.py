import enum
from uuid import UUID

from pydantic import BaseModel, Field


class RetrievalIntent(str, enum.Enum):
    knowledge_lookup = "knowledge_lookup"
    material_recommend = "material_recommend"
    module_suggestion = "module_suggestion"
    trace_lookup = "trace_lookup"
    directory_match = "directory_match"


class RetrievalObjectType(str, enum.Enum):
    ku = "ku"
    wiki = "wiki"
    template = "template"
    template_chapter = "template_chapter"
    bid_outline = "bid_outline"
    bid_outline_node = "bid_outline_node"
    chapter_pattern = "chapter_pattern"
    manual_asset = "manual_asset"


class OutlineNode(BaseModel):
    title: str
    level: int = 1
    sort_order: int = 0
    parent_id: UUID | None = None


class TenderRequirementContext(BaseModel):
    outline_title: str = ""
    score_points: list[str] = Field(default_factory=list)
    rejection_clauses: list[str] = Field(default_factory=list)
    format_requirements: list[str] = Field(default_factory=list)


class RetrievalOptions(BaseModel):
    strategy_version_id: UUID | None = None
    enable_bm25: bool = True
    enable_vector: bool = True
    enable_rerank: bool = False
    top_k: int = 20
    context_expand_depth: int = 1


class ReturnOptions(BaseModel):
    include_trace: bool = True
    include_score_detail: bool = True
    include_conflict_flags: bool = False
    include_knowledge_pack: bool = True


class KnowledgePackItem(BaseModel):
    object_type: RetrievalObjectType
    object_id: UUID
    title: str
    score: float = 0.0
    score_detail: dict = Field(default_factory=dict)
    hit_reason: str | None = None
    source_trace: dict = Field(default_factory=dict)


class RetrievalRequest(BaseModel):
    query: str = ""
    intent: RetrievalIntent
    product_category_ids: list[UUID] = Field(default_factory=list)
    chapter_taxonomy_ids: list[UUID] = Field(default_factory=list)
    knowledge_types: list[str] = Field(default_factory=list)
    file_purposes: list[str] = Field(default_factory=list)
    object_types: list[RetrievalObjectType] = Field(default_factory=list)
    tender_requirement_context: TenderRequirementContext = Field(
        default_factory=TenderRequirementContext
    )
    outline_nodes: list[OutlineNode] = Field(default_factory=list)
    retrieval_options: RetrievalOptions = Field(default_factory=RetrievalOptions)
    return_options: ReturnOptions = Field(default_factory=ReturnOptions)
