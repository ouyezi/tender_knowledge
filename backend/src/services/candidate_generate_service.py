from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeType
from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.chapter_candidate_rules import resolve_candidate_type
from src.services.section_content_builder import build_section_direct_content


def generate_for_document(
    db: Session,
    *,
    kb_id: uuid.UUID,
    import_id: uuid.UUID,
    document_id: uuid.UUID,
    parse_task_id: uuid.UUID | None = None,
) -> list[CandidateKnowledge]:
    heading_nodes = (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == document_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )
    if not heading_nodes:
        return []

    taxonomy_ids = {node.chapter_taxonomy_id for node in heading_nodes if node.chapter_taxonomy_id}
    taxonomy_map: dict[uuid.UUID, str] = {}
    if taxonomy_ids:
        rows = (
            db.query(ChapterTaxonomy.taxonomy_id, ChapterTaxonomy.taxonomy_code)
            .filter(ChapterTaxonomy.taxonomy_id.in_(taxonomy_ids))
            .all()
        )
        taxonomy_map = {row.taxonomy_id: row.taxonomy_code for row in rows}

    existing_source_ids = {
        source_node_id
        for (source_node_id,) in db.query(CandidateKnowledge.source_node_id)
        .filter(
            CandidateKnowledge.kb_id == kb_id,
            CandidateKnowledge.import_id == import_id,
            CandidateKnowledge.source_doc_id == document_id,
        )
        .all()
    }

    created: list[CandidateKnowledge] = []
    for node in heading_nodes:
        if node.node_id in existing_source_ids:
            continue
        taxonomy_code = taxonomy_map.get(node.chapter_taxonomy_id) if node.chapter_taxonomy_id else None
        resolution = resolve_candidate_type(taxonomy_code=taxonomy_code)
        try:
            candidate_type = CandidateKnowledgeType(resolution.candidate_type)
        except ValueError:
            candidate_type = CandidateKnowledgeType.ignore
        if candidate_type == CandidateKnowledgeType.ignore:
            continue

        candidate = CandidateKnowledge(
            kb_id=kb_id,
            import_id=import_id,
            source_doc_id=document_id,
            source_node_id=node.node_id,
            candidate_type=candidate_type,
            title=(node.title or "未命名章节").strip(),
            content=build_section_direct_content(
                db,
                document_id=document_id,
                heading_node_id=node.node_id,
            ),
            summary=None,
            suggested_knowledge_type=resolution.suggested_knowledge_type,
            suggested_chapter_taxonomy_id=node.chapter_taxonomy_id,
            suggested_product_category_ids=node.product_category_ids or [],
            confidence_score=None,
            suggestion_source="rule",
            parse_task_id=parse_task_id,
        )
        db.add(candidate)
        created.append(candidate)

    db.flush()
    return created
