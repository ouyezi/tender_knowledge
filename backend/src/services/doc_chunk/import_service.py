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

_KNOWLEDGE_ENTRY_PURPOSES = frozenset({FilePurpose.actual_bid, FilePurpose.template_file})


def document_source_type_for_purpose(file_purpose: FilePurpose) -> DocumentSourceType:
    if file_purpose == FilePurpose.template_file:
        return DocumentSourceType.template_file
    if file_purpose == FilePurpose.actual_bid:
        return DocumentSourceType.actual_bid
    raise DocChunkImportError(
        f"unsupported file purpose for doc_chunk import: {file_purpose.value}",
        code="DOC_CHUNK_IMPORT_FAILED",
    )


def _assert_knowledge_entry_purpose(file_import: FileImport) -> None:
    if file_import.file_purpose not in _KNOWLEDGE_ENTRY_PURPOSES:
        raise DocChunkImportError(
            f"file_import must be one of {[p.value for p in _KNOWLEDGE_ENTRY_PURPOSES]}",
            code="DOC_CHUNK_IMPORT_FAILED",
        )


def _resolve_document(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    document_id: UUID | None,
    file_import: FileImport,
    source_type: DocumentSourceType,
) -> Document:
    document = db.get(Document, document_id) if document_id is not None else None
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
            source_type=source_type,
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
    document.source_type = source_type
    return document


def import_workspace_for_knowledge_entry(
    db: Session,
    *,
    kb_id: UUID,
    import_id: UUID,
    workspace: Path,
    file_import: FileImport,
    document_id: UUID | None = None,
    persist_outline: bool = False,
    persist_candidates: bool = False,
    parse_task_id: UUID | None = None,
) -> ImportResult:
    """Import doc_chunk workspace for knowledge entry (tree + content.md), without bid-only side effects."""
    _assert_knowledge_entry_purpose(file_import)
    source_type = document_source_type_for_purpose(file_import.file_purpose)

    loaded = load_workspace(workspace)
    ctx = ImportContext(workspace_path=loaded.root)
    warnings = list(loaded.manifest.get("warnings") or [])
    workspace_content_md = loaded.root / "content.md"
    if workspace_content_md.is_file():
        ctx.content_md = workspace_content_md.read_text(encoding="utf-8")

    document = _resolve_document(
        db,
        kb_id=kb_id,
        import_id=import_id,
        document_id=document_id,
        file_import=file_import,
        source_type=source_type,
    )

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

    classify_heading_nodes_for_document(
        db,
        kb_id=kb_id,
        document_id=document.document_id,
    )

    created_candidates: list = []
    if persist_candidates:
        if parse_task_id is None:
            raise DocChunkImportError("parse_task_id required when persist_candidates", code="DOC_CHUNK_IMPORT_FAILED")
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

    document.parse_status = DocumentParseStatus.ready

    extract_strategy = map_outline_strategy(loaded.outline.get("strategy"))
    bid_outline_id = (
        outline_result.bid_outline.bid_outline_id
        if outline_result is not None
        else document.document_id
    )

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

    result = import_workspace_for_knowledge_entry(
        db,
        kb_id=kb_id,
        import_id=import_id,
        workspace=workspace,
        file_import=file_import,
        document_id=document_id,
        persist_outline=persist_outline,
        persist_candidates=True,
        parse_task_id=parse_task_id,
    )

    loaded = load_workspace(workspace)
    warnings = list(result.warnings or [])
    extract_strategy = map_outline_strategy(loaded.outline.get("strategy"))
    classification_summary = classify_heading_nodes_for_document(
        db,
        kb_id=kb_id,
        document_id=result.document_id,
    )

    suggestion = (
        db.query(DocumentParseSuggestion)
        .filter(DocumentParseSuggestion.parse_task_id == parse_task_id)
        .one_or_none()
    )
    if suggestion is None:
        suggestion = DocumentParseSuggestion(
            kb_id=kb_id,
            parse_task_id=parse_task_id,
            document_id=result.document_id,
        )
        db.add(suggestion)
    suggestion.document_id = result.document_id
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
        "candidate_count": result.candidate_count,
    }

    task.document_id = result.document_id
    if persist_outline:
        task.bid_outline_id = result.bid_outline_id

    return result
