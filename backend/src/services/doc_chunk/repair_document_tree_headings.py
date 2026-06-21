from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import Settings
from src.models.document import Document, DocumentParseStatus
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport
from src.services.doc_chunk.outline_heading_correction import (
    apply_outline_heading_corrections,
    infer_outline_node_map_from_headings,
)
from src.services.doc_chunk.outline_store import (
    load_outline,
    load_outline_node_map,
    persist_outline,
    persist_outline_node_map,
)
from src.services.doc_chunk.pipeline_runner import run_doc_chunk_pipeline
from src.services.doc_chunk.workspace_loader import load_workspace
from src.services.docm_converter import ensure_docx_for_parse

logger = logging.getLogger(__name__)


def _load_headings(db: Session, *, document_id: UUID) -> list[DocumentTreeNode]:
    return (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.document_id == document_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(DocumentTreeNode.sort_order.asc(), DocumentTreeNode.created_at.asc())
        .all()
    )


def _resolve_outline_payload(
    db: Session,
    *,
    document: Document,
    storage_root: Path | None = None,
) -> tuple[dict, dict[str, UUID], dict | None]:
    stored_outline = load_outline(document_id=document.document_id, storage_root=storage_root)
    stored_map = load_outline_node_map(document_id=document.document_id, storage_root=storage_root)
    if stored_outline and stored_map:
        return stored_outline, stored_map, None

    file_import = db.get(FileImport, document.import_id)
    if file_import is None:
        raise ValueError(f"file import not found for document {document.document_id}")

    storage_root = storage_root or Path(Settings().storage_root)
    source_path = storage_root / file_import.storage_path
    docx_path = ensure_docx_for_parse(source_path)
    if not docx_path.is_file():
        raise FileNotFoundError(str(docx_path))

    with tempfile.TemporaryDirectory(prefix="doc-chunk-repair-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        run_doc_chunk_pipeline(docx_path, workspace)
        loaded = load_workspace(workspace)
        headings = _load_headings(db, document_id=document.document_id)
        outline_map = stored_map or infer_outline_node_map_from_headings(
            loaded.outline,
            headings,
            tree_payload=loaded.document_tree,
        )
        return loaded.outline, outline_map, loaded.document_tree


def repair_document_tree_headings(
    db: Session,
    *,
    document_id: UUID,
    storage_root: Path | None = None,
) -> int:
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError(f"document not found: {document_id}")
    if document.parse_status != DocumentParseStatus.ready:
        logger.info("skip repair for non-ready document_id=%s status=%s", document_id, document.parse_status)
        return 0

    outline_payload, outline_map, regenerated_tree = _resolve_outline_payload(
        db,
        document=document,
        storage_root=storage_root,
    )
    if not outline_map:
        outline_map = infer_outline_node_map_from_headings(
            outline_payload,
            _load_headings(db, document_id=document.document_id),
            tree_payload=regenerated_tree,
        )
    if not outline_map:
        logger.warning("repair skipped: unable to map outline nodes document_id=%s", document_id)
        return 0

    updated = apply_outline_heading_corrections(
        db,
        document_id=document.document_id,
        outline_payload=outline_payload,
        outline_node_to_tree_id=outline_map,
    )
    persist_outline(
        document_id=document.document_id,
        outline_payload=outline_payload,
        storage_root=storage_root,
    )
    persist_outline_node_map(
        document_id=document.document_id,
        outline_node_to_tree_id=outline_map,
        storage_root=storage_root,
    )
    return updated


def repair_all_ready_document_trees(db: Session, *, storage_root: Path | None = None) -> dict[str, int]:
    documents = (
        db.query(Document)
        .filter(Document.parse_status == DocumentParseStatus.ready)
        .order_by(Document.updated_at.asc())
        .all()
    )
    summary = {"documents": 0, "updated_nodes": 0, "failed": 0}
    for document in documents:
        summary["documents"] += 1
        try:
            updated = repair_document_tree_headings(
                db,
                document_id=document.document_id,
                storage_root=storage_root,
            )
            summary["updated_nodes"] += updated
            db.commit()
        except Exception:
            db.rollback()
            summary["failed"] += 1
            logger.exception("repair failed document_id=%s", document.document_id)
    logger.info("repair_all_ready_document_trees summary=%s", summary)
    return summary
