from __future__ import annotations

from pydantic import BaseModel


class KnowledgeTaxonomyItem(BaseModel):
    code: str
    dimension: str
    parent_code: str | None = None
    label: str
    label_en: str | None = None
    level: int
    sort_order: int
    is_active: bool
