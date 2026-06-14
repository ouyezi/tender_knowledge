from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus
from src.schemas.retrieval import RetrievalRequest


@dataclass(slots=True)
class MetadataRecallHit:
    entry: RetrievalIndexEntry
    score: float
    reason: str


class MetadataRecallService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def recall(self, *, kb_id: UUID, request: RetrievalRequest, top_k: int) -> list[MetadataRecallHit]:
        rows = (
            self.db.query(RetrievalIndexEntry)
            .filter(
                RetrievalIndexEntry.kb_id == kb_id,
                RetrievalIndexEntry.status == RetrievalIndexStatus.published,
            )
            .all()
        )
        hits: list[MetadataRecallHit] = []
        for row in rows:
            score = 0.0
            reasons: list[str] = []
            if self._match_object_types(row, request):
                score += 0.25
                reasons.append("对象类型匹配")
            else:
                continue
            if self._match_categories(row, request):
                score += 0.35
                reasons.append("产品分类匹配")
            elif request.product_category_ids:
                continue
            if self._match_chapter_taxonomy(row, request):
                score += 0.2
                reasons.append("章节分类匹配")
            elif request.chapter_taxonomy_ids:
                continue
            if self._match_knowledge_type(row, request):
                score += 0.1
                reasons.append("知识类型匹配")
            elif request.knowledge_types:
                continue
            if self._match_file_purpose(row, request):
                score += 0.1
                reasons.append("素材用途匹配")
            elif request.file_purposes:
                continue
            hits.append(
                MetadataRecallHit(
                    entry=row,
                    score=round(min(1.0, score), 4),
                    reason="，".join(reasons) if reasons else "元数据匹配",
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    @staticmethod
    def _match_object_types(row: RetrievalIndexEntry, request: RetrievalRequest) -> bool:
        if not request.object_types:
            return True
        return row.object_type.value in {item.value for item in request.object_types}

    @staticmethod
    def _match_categories(row: RetrievalIndexEntry, request: RetrievalRequest) -> bool:
        if not request.product_category_ids:
            return True
        request_set = {str(item) for item in request.product_category_ids}
        return bool(request_set.intersection({str(item) for item in (row.product_category_ids or [])}))

    @staticmethod
    def _match_chapter_taxonomy(row: RetrievalIndexEntry, request: RetrievalRequest) -> bool:
        if not request.chapter_taxonomy_ids:
            return True
        if row.chapter_taxonomy_id is None:
            return False
        return str(row.chapter_taxonomy_id) in {str(item) for item in request.chapter_taxonomy_ids}

    @staticmethod
    def _match_knowledge_type(row: RetrievalIndexEntry, request: RetrievalRequest) -> bool:
        if not request.knowledge_types:
            return True
        return (row.knowledge_type or "") in set(request.knowledge_types)

    @staticmethod
    def _match_file_purpose(row: RetrievalIndexEntry, request: RetrievalRequest) -> bool:
        if not request.file_purposes:
            return True
        return (row.file_purpose or "") in set(request.file_purposes)
