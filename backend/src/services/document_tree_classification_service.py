from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.chunk_classification_service import classify_chunk
from src.services.classification_rule_index import load_classification_index
from src.services.knowledge_chunk import KnowledgeChunk


@dataclass
class DocumentTreeClassificationSummary:
    heading_count: int
    taxonomy_assigned_count: int
    product_category_assigned_count: int
    degraded_to_rule_count: int

    def to_payload(self, *, use_llm: bool) -> dict:
        return {
            "mode": "rule_or_hybrid" if use_llm else "rule_only",
            "heading_count": self.heading_count,
            "taxonomy_assigned_count": self.taxonomy_assigned_count,
            "product_category_assigned_count": self.product_category_assigned_count,
            "degraded_to_rule_count": self.degraded_to_rule_count,
        }


def classify_heading_nodes_for_document(
    db: Session,
    *,
    kb_id: UUID,
    document_id: UUID,
    use_llm: bool = False,
    commit_batch_size: int = 100,
    on_progress: Callable[[int, int], None] | None = None,
) -> DocumentTreeClassificationSummary:
    headings = (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == document_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    if not headings:
        return DocumentTreeClassificationSummary(
            heading_count=0,
            taxonomy_assigned_count=0,
            product_category_assigned_count=0,
            degraded_to_rule_count=0,
        )

    index = load_classification_index(db, kb_id=kb_id)
    taxonomy_assigned = 0
    product_assigned = 0
    degraded_count = 0

    total = len(headings)
    for idx, node in enumerate(headings, start=1):
        title = (node.title or "未命名章节").strip()
        preview = (node.content_preview or title).strip()[:8000]

        chunk = KnowledgeChunk(
            chunk_ref=str(node.node_id),
            chunk_type="candidate",
            title=title,
            content_preview=preview,
        )
        result, degraded = classify_chunk(
            db,
            kb_id=kb_id,
            chunk=chunk,
            index=index,
            use_llm=use_llm,
        )
        if degraded:
            degraded_count += 1

        if result.suggested_chapter_taxonomy_id is not None:
            node.chapter_taxonomy_id = result.suggested_chapter_taxonomy_id
            taxonomy_assigned += 1
        if result.suggested_product_category_ids:
            node.product_category_ids = [str(item) for item in result.suggested_product_category_ids]
            product_assigned += 1

        if commit_batch_size > 0 and idx % commit_batch_size == 0:
            db.commit()
        if on_progress is not None:
            on_progress(idx, total)

    db.flush()
    return DocumentTreeClassificationSummary(
        heading_count=len(headings),
        taxonomy_assigned_count=taxonomy_assigned,
        product_category_assigned_count=product_assigned,
        degraded_to_rule_count=degraded_count,
    )
