from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, literal, or_, text
from sqlalchemy.orm import Session

from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus


@dataclass(slots=True)
class KeywordRecallHit:
    entry: RetrievalIndexEntry
    score: float
    reason: str


class KeywordRecallService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def recall(self, *, kb_id: UUID, query: str, top_k: int) -> list[KeywordRecallHit]:
        query_text = (query or "").strip()
        if not query_text:
            return []
        if self._is_postgresql():
            return self._postgres_recall(kb_id=kb_id, query_text=query_text, top_k=top_k)
        return self._fallback_recall(kb_id=kb_id, query_text=query_text, top_k=top_k)

    def _postgres_recall(self, *, kb_id: UUID, query_text: str, top_k: int) -> list[KeywordRecallHit]:
        # PostgreSQL优先使用tsvector/ts_rank；异常时降级到ILIKE，保证测试环境可跑通。
        ts_query = func.plainto_tsquery("simple", query_text)
        search_doc = func.to_tsvector(
            "simple",
            func.concat(
                func.coalesce(RetrievalIndexEntry.title, literal("")),
                literal(" "),
                func.coalesce(RetrievalIndexEntry.content_text, literal("")),
            ),
        )
        rank_expr = func.ts_rank(search_doc, ts_query)
        try:
            rows = (
                self.db.query(RetrievalIndexEntry, rank_expr.label("rank_score"))
                .filter(
                    RetrievalIndexEntry.kb_id == kb_id,
                    RetrievalIndexEntry.status == RetrievalIndexStatus.published,
                    search_doc.op("@@")(ts_query),
                )
                .order_by(text("rank_score DESC"))
                .limit(max(1, top_k))
                .all()
            )
        except Exception:  # pragma: no cover - 仅在PG能力缺失时触发
            self.db.rollback()
            return self._fallback_recall(kb_id=kb_id, query_text=query_text, top_k=top_k)
        return [
            KeywordRecallHit(
                entry=item[0],
                score=round(float(item[1] or 0.0), 4),
                reason="关键词全文匹配",
            )
            for item in rows
        ]

    def _fallback_recall(self, *, kb_id: UUID, query_text: str, top_k: int) -> list[KeywordRecallHit]:
        pattern = f"%{query_text}%"
        rows = (
            self.db.query(RetrievalIndexEntry)
            .filter(
                RetrievalIndexEntry.kb_id == kb_id,
                RetrievalIndexEntry.status == RetrievalIndexStatus.published,
                or_(
                    RetrievalIndexEntry.title.ilike(pattern),
                    RetrievalIndexEntry.content_text.ilike(pattern),
                ),
            )
            .limit(max(1, top_k) * 2)
            .all()
        )
        hits: list[KeywordRecallHit] = []
        for row in rows:
            title = (row.title or "").lower()
            content = (row.content_text or "").lower()
            token = query_text.lower()
            title_hit = 1.0 if token in title else 0.0
            content_hit = min(1.0, content.count(token) * 0.2)
            score = round(min(1.0, 0.7 * title_hit + 0.3 * content_hit), 4)
            hits.append(KeywordRecallHit(entry=row, score=score, reason="关键词模糊匹配"))
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    def _is_postgresql(self) -> bool:
        return self.db.get_bind().dialect.name == "postgresql"
