from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.bid_outline_node import BidOutlineNode, BidOutlineNodeStatus
from src.models.chapter_pattern import ChapterPattern, ChapterPatternStatus
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.services.retrieval.title_normalizer import normalize_outline_title


@dataclass(slots=True)
class StructureRecallResult:
    matched_outline_ids: list[UUID]
    matched_template_chapter_ids: list[UUID]
    matched_pattern_ids: list[UUID]
    title_similarity_score: float
    level_order_score: float
    chapter_taxonomy_score: float
    candidate_patterns: list[dict]


class StructureRecallService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def recall(
        self,
        *,
        kb_id: UUID,
        outline_nodes: list[dict],
        product_category_ids: list[str],
        top_k: int = 10,
    ) -> StructureRecallResult:
        normalized_titles = {
            normalize_outline_title(str(item.get("title", "")))
            for item in outline_nodes
            if str(item.get("title", "")).strip()
        }
        levels = [int(item.get("level", 1)) for item in outline_nodes] or [1]
        min_level = min(levels)
        max_level = max(levels)

        outline_rows = (
            self.db.query(BidOutlineNode)
            .filter(BidOutlineNode.kb_id == kb_id, BidOutlineNode.status == BidOutlineNodeStatus.confirmed)
            .all()
        )
        template_rows = (
            self.db.query(TemplateChapter)
            .filter(TemplateChapter.kb_id == kb_id, TemplateChapter.status == TemplateChapterStatus.published)
            .all()
        )
        pattern_rows = (
            self.db.query(ChapterPattern)
            .filter(ChapterPattern.kb_id == kb_id, ChapterPattern.status == ChapterPatternStatus.confirmed)
            .order_by(ChapterPattern.frequency.desc())
            .limit(max(top_k, 1) * 3)
            .all()
        )

        matched_outline_ids = [
            row.outline_node_id
            for row in outline_rows
            if self._title_match(row.title, normalized_titles)
            and self._category_match(row.product_category_ids or [], product_category_ids)
        ][:top_k]
        matched_template_chapter_ids = [
            row.template_chapter_id
            for row in template_rows
            if self._title_match(row.title, normalized_titles)
            and self._category_match(row.product_category_ids or [], product_category_ids)
        ][:top_k]
        matched_pattern_ids = [
            row.pattern_id
            for row in pattern_rows
            if self._title_match(row.pattern_name, normalized_titles)
            and self._category_match(row.product_category_ids or [], product_category_ids)
        ][:top_k]

        title_hit_count = len(matched_outline_ids) + len(matched_template_chapter_ids) + len(matched_pattern_ids)
        title_similarity_score = 0.0 if not normalized_titles else min(1.0, title_hit_count / max(len(normalized_titles), 1))

        matched_levels = [row.level for row in outline_rows if row.outline_node_id in set(matched_outline_ids)]
        level_order_score = self._level_score(min_level, max_level, matched_levels)

        taxonomy_hits = [
            row for row in template_rows if row.template_chapter_id in set(matched_template_chapter_ids) and row.chapter_taxonomy_id
        ]
        chapter_taxonomy_score = 1.0 if taxonomy_hits else 0.0

        candidate_patterns = [
            {"pattern_id": row.pattern_id, "pattern_name": row.pattern_name, "frequency": row.frequency}
            for row in pattern_rows
            if self._category_match(row.product_category_ids or [], product_category_ids)
        ]
        return StructureRecallResult(
            matched_outline_ids=matched_outline_ids,
            matched_template_chapter_ids=matched_template_chapter_ids,
            matched_pattern_ids=matched_pattern_ids,
            title_similarity_score=round(title_similarity_score, 4),
            level_order_score=round(level_order_score, 4),
            chapter_taxonomy_score=round(chapter_taxonomy_score, 4),
            candidate_patterns=candidate_patterns,
        )

    @staticmethod
    def _title_match(candidate_title: str, normalized_titles: set[str]) -> bool:
        normalized_candidate = normalize_outline_title(candidate_title or "")
        if not normalized_candidate:
            return False
        return normalized_candidate in normalized_titles

    @staticmethod
    def _category_match(candidate_categories: list, request_categories: list[str]) -> bool:
        if not request_categories:
            return True
        request_set = {str(item) for item in request_categories}
        return bool(request_set.intersection({str(item) for item in candidate_categories}))

    @staticmethod
    def _level_score(min_level: int, max_level: int, matched_levels: list[int]) -> float:
        if not matched_levels:
            return 0.0
        level_span = max(max_level - min_level, 1)
        aligned = [1.0 - (abs(level - min_level) / level_span) for level in matched_levels]
        return max(0.0, min(1.0, sum(aligned) / len(aligned)))
