from __future__ import annotations

from src.models.retrieval_index_entry import RetrievalIndexEntry


class KnowledgePackBuilder:
    def build(self, entry: RetrievalIndexEntry, *, score: float, score_detail: dict, hit_reason: str) -> dict:
        return {
            "object_type": entry.object_type.value,
            "object_id": str(entry.object_id),
            "title": entry.title,
            "score": round(score, 4),
            "score_detail": score_detail,
            "hit_reason": hit_reason,
            "source_trace": {
                "import_id": str(entry.import_id) if entry.import_id else None,
                "source_doc_id": str(entry.source_doc_id) if entry.source_doc_id else None,
                "source_node_id": str(entry.source_node_id) if entry.source_node_id else None,
            },
            "knowledge_pack": {
                "product_category_ids": entry.product_category_ids or [],
                "chapter_taxonomy_id": str(entry.chapter_taxonomy_id) if entry.chapter_taxonomy_id else None,
                "knowledge_type": entry.knowledge_type,
                "file_purpose": entry.file_purpose,
                "hit_reason": hit_reason,
            },
        }
