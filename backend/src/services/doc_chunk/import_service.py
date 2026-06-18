from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_parse_suggestion import DocumentParseSuggestion
from src.models.file_import import FileImport, FilePurpose
from src.services.document_tree_classification_service import classify_heading_nodes_for_document
from src.config import Settings
from src.services.doc_chunk.content_md_store import persist_content_md, persist_image_ref_map
from src.services.doc_chunk.mappers.bid_outline import import_bid_outline, map_outline_strategy
from src.services.doc_chunk.mappers.candidates import import_candidates
from src.services.doc_chunk.mappers.document_tree import import_document_tree
from src.services.doc_chunk.mappers.enrich_document_tree import enrich_document_tree_from_chunks
from src.services.doc_chunk.mappers.media_assets import import_media_assets
from src.services.doc_chunk.types import DocChunkImportError, ImportContext, ImportResult
from src.services.doc_chunk.workspace_loader import load_workspace
from src.services.knowledge_v2.asset_seed_service import seed_chunk_assets_from_workspace


def import_workspace(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    document_id: UUID | None,
    parse_task_id: UUID,
    workspace: Path,
    file_import: FileImport,
    task: ActualBidParseTask,
    persist_outline: bool = True,
) -> ImportResult:
    if file_import.file_purpose != FilePurpose.actual_bid:
        raise DocChunkImportError("file_import must be actual_bid", code="DOC_CHUNK_IMPORT_FAILED")

    loaded = load_workspace(workspace)
    ctx = ImportContext(workspace_path=loaded.root)
    warnings = list(loaded.manifest.get("warnings") or [])
    workspace_content_md = loaded.root / "content.md"
    if workspace_content_md.is_file():
        ctx.content_md = workspace_content_md.read_text(encoding="utf-8")

    document = None
    if document_id is not None:
        document = db.get(Document, document_id)
    if document is None:
        document = (
            db.query(Document)
            .filter(Document.kb_id == kb_id, Document.import_id == import_id)
            .order_by(Document.created_at.desc())
            .first()
        )
    if document is None:
        document = Document(
            kb_id=kb_id,
            import_id=import_id,
            source_type=DocumentSourceType.actual_bid,
            document_name=file_import.file_name,
            parse_status=DocumentParseStatus.parsing,
            product_category_ids=file_import.product_category_ids or [],
            created_by=file_import.confirmed_by or file_import.created_by or "system",
        )
        db.add(document)
        db.flush()

    document.document_name = file_import.file_name
    document.parse_status = DocumentParseStatus.parsing
    document.product_category_ids = file_import.product_category_ids or []

    if ctx.content_md:
        persist_content_md(
            document_id=document.document_id,
            source_path=workspace_content_md,
            storage_root=Path(Settings().storage_root),
        )

    import_media_assets(db, ctx=ctx, document=document, kb_id=kb_id)
    seed_chunk_assets_from_workspace(
        db,
        kb_id=kb_id,
        doc_id=document.document_id,
        workspace_path=loaded.root,
        image_ref_map=ctx.image_ref_map,
    )
    if ctx.image_ref_map:
        persist_image_ref_map(
            document_id=document.document_id,
            image_ref_map=ctx.image_ref_map,
            storage_root=Path(Settings().storage_root),
        )
    tree_id_map = import_document_tree(
        db,
        ctx=ctx,
        document=document,
        kb_id=kb_id,
        tree_payload=loaded.document_tree,
    )
    enriched_tree_nodes = enrich_document_tree_from_chunks(
        db,
        ctx=ctx,
        document=document,
        kb_id=kb_id,
        outline_payload=loaded.outline,
        linkage_payload=loaded.linkage,
        chunks_index=loaded.chunks_index,
        warnings=warnings,
    )
    if enriched_tree_nodes:
        warnings.append(f"enriched_tree_nodes:{enriched_tree_nodes}")
    outline_result = None
    outline_node_count = 0
    if persist_outline:
        outline_result = import_bid_outline(
            db,
            ctx=ctx,
            kb_id=kb_id,
            import_id=import_id,
            document_id=document.document_id,
            outline_name=document.document_name,
            outline_payload=loaded.outline,
            linkage_payload=loaded.linkage,
            created_by=file_import.confirmed_by or file_import.created_by or "system",
            product_category_ids=file_import.product_category_ids or [],
            project_name=document.bid_project_name,
            customer_name=document.bid_customer_name,
        )
        outline_node_count = outline_result.node_count
        task.bid_outline_id = outline_result.bid_outline.bid_outline_id

    classification_summary = classify_heading_nodes_for_document(
        db,
        kb_id=kb_id,
        document_id=document.document_id,
    )

    created_candidates = import_candidates(
        db,
        ctx=ctx,
        kb_id=kb_id,
        import_id=import_id,
        document_id=document.document_id,
        parse_task_id=parse_task_id,
        outline_payload=loaded.outline,
        linkage_payload=loaded.linkage,
        chunks_index=loaded.chunks_index,
        warnings=warnings,
    )

    extract_strategy = map_outline_strategy(loaded.outline.get("strategy"))
    suggestion = (
        db.query(DocumentParseSuggestion)
        .filter(DocumentParseSuggestion.parse_task_id == parse_task_id)
        .one_or_none()
    )
    if suggestion is None:
        suggestion = DocumentParseSuggestion(
            kb_id=kb_id,
            parse_task_id=parse_task_id,
            document_id=document.document_id,
        )
        db.add(suggestion)
    suggestion.document_id = document.document_id
    suggestion.payload = {
        "outline_extract_strategy": extract_strategy.value,
        "parse_engine": "doc_chunk",
        "doc_chunk": {
            "schema_version": loaded.manifest.get("schema_version"),
            "manifest_status": loaded.manifest.get("status"),
            "warnings": warnings,
        },
        "outline_quality": {
            "strategy": loaded.outline.get("strategy"),
            "outline_node_count": len(loaded.outline.get("nodes") or []),
            "tree_node_count": len(loaded.document_tree.get("nodes") or []),
            "chunk_count": len(loaded.chunks_index.get("chunks") or []),
        },
        "chunk_classification": classification_summary.to_payload(use_llm=False),
        "candidate_count": len(created_candidates),
    }

    document.parse_status = DocumentParseStatus.ready
    task.document_id = document.document_id

    bid_outline_id = outline_result.bid_outline.bid_outline_id if outline_result else (task.bid_outline_id or document.document_id)

    return ImportResult(
        document_id=document.document_id,
        bid_outline_id=bid_outline_id,
        tree_node_count=len(tree_id_map) + enriched_tree_nodes,
        outline_node_count=outline_node_count,
        candidate_count=len(created_candidates),
        parse_engine="doc_chunk",
        extract_strategy=extract_strategy.value,
        tree_id_map=dict(ctx.tree_id_map),
        warnings=warnings,
    )
