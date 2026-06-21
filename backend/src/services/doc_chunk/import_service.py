from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import Settings
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.file_import import FileImport, FilePurpose
from src.services.doc_chunk.content_md_store import persist_content_md, persist_image_ref_map
from src.services.doc_chunk.mappers.document_tree import import_document_tree
from src.services.doc_chunk.mappers.enrich_document_tree import enrich_document_tree_from_chunks
from src.services.doc_chunk.mappers.media_assets import import_media_assets
from src.services.doc_chunk.types import DocChunkImportError, ImportContext, ImportResult
from src.services.doc_chunk.workspace_loader import load_workspace
from src.services.knowledge.asset_seed_service import seed_chunk_assets_from_workspace

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
) -> ImportResult:
    """Import doc_chunk workspace for knowledge entry (tree + content.md + chunk assets)."""
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

    document.parse_status = DocumentParseStatus.ready

    return ImportResult(
        document_id=document.document_id,
        tree_node_count=len(tree_id_map) + enriched_tree_nodes,
        parse_engine="doc_chunk",
        tree_id_map=dict(ctx.tree_id_map),
        warnings=warnings,
    )
