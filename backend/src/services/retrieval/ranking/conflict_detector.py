from __future__ import annotations

from src.models.template_chapter import TemplateChapter


class ConflictDetector:
    def detect(
        self,
        *,
        template_chapters: list[TemplateChapter],
        rejection_clauses: list[str],
    ) -> tuple[set[str], list[dict[str, str]]]:
        if not rejection_clauses:
            return set(), []
        rejected_tokens = self._extract_tokens(rejection_clauses)
        conflict_ids: set[str] = set()
        risk_flags: list[dict[str, str]] = []
        for chapter in template_chapters:
            title = (chapter.title or "").strip()
            if not title:
                continue
            for token in rejected_tokens:
                if token in title:
                    chapter_id = str(chapter.template_chapter_id)
                    conflict_ids.add(chapter_id)
                    risk_flags.append(
                        {
                            "template_chapter_id": chapter_id,
                            "risk_type": "tender_template_conflict",
                            "reason": f"招标约束命中敏感词：{token}",
                        }
                    )
                    break
        return conflict_ids, risk_flags

    @staticmethod
    def _extract_tokens(rejection_clauses: list[str]) -> set[str]:
        tokens: set[str] = set()
        for clause in rejection_clauses:
            text = (clause or "").strip()
            if not text:
                continue
            for token in ("原厂授权", "唯一厂家", "排他", "独家", "指定品牌"):
                if token in text:
                    tokens.add(token)
        return tokens
