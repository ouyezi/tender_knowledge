from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from src.models.chapter_taxonomy import ChapterTaxonomy, ChapterTaxonomySynonym, CategoryStatus
from src.models.product_category import ProductCategory, ProductCategoryAlias
from src.services.alias_registry import normalize


@dataclass
class MatchedProductCategory:
    category_id: UUID
    confidence: float
    rationale: str


@dataclass
class MatchedChapterTaxonomy:
    taxonomy_id: UUID
    confidence: float
    rationale: str


@dataclass
class ClassificationRuleIndex:
    product_terms: list[tuple[UUID, str]] = field(default_factory=list)
    taxonomy_terms: list[tuple[UUID, str]] = field(default_factory=list)


def load_classification_index(db: Session, *, kb_id: UUID) -> ClassificationRuleIndex:
    index = ClassificationRuleIndex()
    categories = (
        db.query(ProductCategory)
        .options(joinedload(ProductCategory.aliases))
        .filter(
            ProductCategory.kb_id == kb_id,
            ProductCategory.status == CategoryStatus.active,
        )
        .all()
    )
    for category in categories:
        index.product_terms.append((category.category_id, normalize(category.category_name)))
        for alias in category.aliases:
            index.product_terms.append((category.category_id, alias.alias_normalized))

    taxonomies = (
        db.query(ChapterTaxonomy)
        .options(joinedload(ChapterTaxonomy.synonyms))
        .filter(
            ChapterTaxonomy.kb_id == kb_id,
            ChapterTaxonomy.status == CategoryStatus.active,
        )
        .all()
    )
    for taxonomy in taxonomies:
        index.taxonomy_terms.append((taxonomy.taxonomy_id, normalize(taxonomy.standard_name)))
        for synonym in taxonomy.synonyms:
            index.taxonomy_terms.append((taxonomy.taxonomy_id, synonym.synonym_normalized))
    return index


def _best_term_match(
    text: str,
    terms: list[tuple[UUID, str]],
    *,
    label: str,
) -> tuple[UUID, float, str] | None:
    normalized_text = normalize(text)
    if not normalized_text:
        return None
    best: tuple[UUID, float, str] | None = None
    for entity_id, term in terms:
        if not term or term not in normalized_text:
            continue
        confidence = 0.9 if normalized_text == term else 0.82
        candidate = (entity_id, confidence, f"{label}命中：{term}")
        if best is None or candidate[1] > best[1]:
            best = candidate
    return best


def match_product_category(text: str, *, index: ClassificationRuleIndex) -> MatchedProductCategory | None:
    hit = _best_term_match(text, index.product_terms, label="产品分类")
    if hit is None:
        return None
    return MatchedProductCategory(category_id=hit[0], confidence=hit[1], rationale=hit[2])


def match_chapter_taxonomy(text: str, *, index: ClassificationRuleIndex) -> MatchedChapterTaxonomy | None:
    hit = _best_term_match(text, index.taxonomy_terms, label="章节类型")
    if hit is None:
        return None
    return MatchedChapterTaxonomy(taxonomy_id=hit[0], confidence=hit[1], rationale=hit[2])
