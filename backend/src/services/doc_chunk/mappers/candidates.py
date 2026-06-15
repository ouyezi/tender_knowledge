from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeStatus, CandidateKnowledgeType
from src.models.chapter_taxonomy import ChapterTaxonomy
from src.services.chapter_candidate_rules import resolve_candidate_type
from src.services.doc_chunk.blocks_v1 import chunk_blocks_to_content
from src.services.doc_chunk.types import DocChunkImportError, ImportContext
from src.services.doc_chunk.workspace_loader import load_chunk_file


def _resolve_candidate_type_from_metadata(metadata: dict[str, Any] | None) -> CandidateKnowledgeType:
    metadata = metadata or {}
    suggested = metadata.get("suggested_candidate_type")
    if suggested:
        try:
            return CandidateKnowledgeType(str(suggested))
        except ValueError:
            pass
    chapter_type = metadata.get("chapter_type")
    resolution = resolve_candidate_type(taxonomy_code=str(chapter_type) if chapter_type else None)
    try:
        return CandidateKnowledgeType(resolution.candidate_type)
    except ValueError:
        return CandidateKnowledgeType.ignore


def _resolve_taxonomy_id(
    db: Session,
    *,
    kb_id: UUID,
    metadata: dict[str, Any] | None,
) -> UUID | None:
    metadata = metadata or {}
    hints = metadata.get("chapter_taxonomy_hints") or []
    if not hints:
        return None
    code = str(hints[0]).strip()
    if not code:
        return None
    row = (
        db.query(ChapterTaxonomy.taxonomy_id)
        .filter(ChapterTaxonomy.kb_id == kb_id, ChapterTaxonomy.taxonomy_code == code)
        .first()
    )
    return row[0] if row else None


def import_candidates(
    db: Session,
    *,
    ctx: ImportContext,
    kb_id: UUID,
    import_id: UUID,
    document_id: UUID,
    parse_task_id: UUID,
    linkage_payload: dict[str, Any],
    chunks_index: dict[str, Any],
    warnings: list[str],
) -> list[CandidateKnowledge]:
    chunk_path_by_id = {
        str(item.get("chunk_id")): str(item.get("path"))
        for item in (chunks_index.get("chunks") or [])
        if item.get("chunk_id") and item.get("path")
    }
    created: list[CandidateKnowledge] = []

    for entry in linkage_payload.get("entries") or []:
        chunk_ids = [str(item) for item in (entry.get("chunk_ids") or [])]
        primary_chunk_id = entry.get("primary_chunk_id") or (chunk_ids[0] if chunk_ids else None)
        if not primary_chunk_id:
            continue

        tree_ids = [str(item) for item in (entry.get("document_tree_node_ids") or [])]
        if not tree_ids:
            outline_id = str(entry.get("outline_node_id") or "")
            if outline_id and outline_id != "flat_fallback":
                raise DocChunkImportError(
                    f"Linkage missing tree node for outline {outline_id}",
                    code="DOC_CHUNK_LINKAGE_INCOMPLETE",
                )
            continue

        source_node_id = ctx.tree_id_map.get(tree_ids[0])
        if source_node_id is None:
            raise DocChunkImportError(
                f"Unknown tree node {tree_ids[0]} in linkage",
                code="DOC_CHUNK_LINKAGE_INCOMPLETE",
            )

        rel_path = chunk_path_by_id.get(str(primary_chunk_id))
        if not rel_path:
            warnings.append(f"missing_chunk:{primary_chunk_id}")
            continue

        chunk_payload = load_chunk_file(ctx.workspace_path, f"chunks/{rel_path}")
        title = str(chunk_payload.get("title") or "").strip() or "未命名章节"
        if title == "Preface":
            continue
        if not chunk_payload.get("original_node_ids"):
            continue

        metadata = chunk_payload.get("metadata") or {}
        candidate_type = _resolve_candidate_type_from_metadata(metadata)
        if candidate_type == CandidateKnowledgeType.ignore:
            continue

        blocks = chunk_payload.get("blocks") or []
        content = chunk_blocks_to_content(blocks, image_ref_map=ctx.image_ref_map)
        taxonomy_id = _resolve_taxonomy_id(db, kb_id=kb_id, metadata=metadata)
        suggestion_source = str(metadata.get("classification_source") or "rule")

        candidate = CandidateKnowledge(
            kb_id=kb_id,
            import_id=import_id,
            source_doc_id=document_id,
            source_node_id=source_node_id,
            candidate_type=candidate_type,
            title=title,
            content=content,
            summary=metadata.get("description"),
            suggested_knowledge_type=metadata.get("suggested_knowledge_type") or metadata.get("knowledge_type"),
            suggested_chapter_taxonomy_id=taxonomy_id,
            suggested_product_category_ids=[],
            confidence_score=metadata.get("classification_confidence"),
            suggestion_source=suggestion_source,
            status=CandidateKnowledgeStatus.pending,
            parse_task_id=parse_task_id,
        )
        db.add(candidate)
        created.append(candidate)

    db.flush()
    return created
