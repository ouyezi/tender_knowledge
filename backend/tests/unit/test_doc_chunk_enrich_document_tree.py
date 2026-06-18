# backend/tests/unit/test_doc_chunk_enrich_document_tree.py
from pathlib import Path
from uuid import uuid4

from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.content_blocks import parse_content
from src.services.doc_chunk.mappers.document_tree import import_document_tree
from src.services.doc_chunk.mappers.enrich_document_tree import enrich_document_tree_from_chunks
from src.services.doc_chunk.mappers.media_assets import import_media_assets
from src.services.doc_chunk.types import ImportContext
from src.services.doc_chunk.workspace_loader import load_workspace
from src.services.section_content_builder import build_section_direct_content

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def _prepare_document(db_session, seeded_kb):
    loaded = load_workspace(FIXTURE_ROOT)
    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=uuid4(),
        source_type=DocumentSourceType.actual_bid,
        document_name="t.docx",
        parse_status=DocumentParseStatus.parsing,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()
    ctx = ImportContext(workspace_path=FIXTURE_ROOT)
    content_md_path = FIXTURE_ROOT / "content.md"
    if content_md_path.is_file():
        ctx.content_md = content_md_path.read_text(encoding="utf-8")
    import_media_assets(db_session, ctx=ctx, document=document, kb_id=seeded_kb.kb_id)
    return loaded, document, ctx


def test_enrich_document_tree_materializes_chunk_blocks_when_heading_has_no_body(db_session, seeded_kb):
    loaded, document, ctx = _prepare_document(db_session, seeded_kb)

    tree_payload = {
        "schema_version": "1.0",
        "nodes": [
            {
                "node_id": "t0001",
                "parent_id": None,
                "outline_node_id": "n1",
                "node_type": "heading",
                "title": "1 项目概述",
                "level": 1,
                "sort_order": 0,
                "text": None,
            }
        ],
    }
    import_document_tree(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        tree_payload=tree_payload,
    )

    warnings: list[str] = []
    created = enrich_document_tree_from_chunks(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        outline_payload=loaded.outline,
        linkage_payload=loaded.linkage,
        chunks_index=loaded.chunks_index,
        warnings=warnings,
    )
    assert created == 4

    heading_id = ctx.tree_id_map["t0001"]
    content = build_section_direct_content(
        db_session,
        document_id=document.document_id,
        heading_node_id=heading_id,
    )
    doc = parse_content(content)
    texts = [b.get("text") for b in doc.blocks if b.get("type") == "paragraph"]
    assert texts[0] == "# 1 项目概述"
    assert "## 1.1 实施范围" in texts


def test_enrich_document_tree_skips_when_body_already_present(db_session, seeded_kb):
    loaded, document, ctx = _prepare_document(db_session, seeded_kb)
    import_document_tree(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        tree_payload=loaded.document_tree,
    )
    heading_with_body = ctx.tree_id_map["t0002"]
    before = (
        db_session.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.parent_id == heading_with_body,
            DocumentTreeNode.node_type != DocumentTreeNodeType.heading,
        )
        .count()
    )
    created = enrich_document_tree_from_chunks(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        outline_payload=loaded.outline,
        linkage_payload=loaded.linkage,
        chunks_index=loaded.chunks_index,
        warnings=[],
    )
    after = (
        db_session.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.parent_id == heading_with_body,
            DocumentTreeNode.node_type != DocumentTreeNodeType.heading,
        )
        .count()
    )
    assert before == 2
    assert after == 2
    assert created == 4


def test_enrich_document_tree_materializes_when_chunk_title_has_number_prefix(db_session, seeded_kb):
    loaded, document, ctx = _prepare_document(db_session, seeded_kb)
    tree_payload = {
        "schema_version": "1.0",
        "nodes": [
            {
                "node_id": "t0001",
                "parent_id": None,
                "outline_node_id": "n1",
                "node_type": "heading",
                "title": "项目概述",
                "level": 1,
                "sort_order": 0,
                "text": None,
            }
        ],
    }
    import_document_tree(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        tree_payload=tree_payload,
    )
    created = enrich_document_tree_from_chunks(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        outline_payload=loaded.outline,
        linkage_payload=loaded.linkage,
        chunks_index=loaded.chunks_index,
        warnings=[],
    )
    assert created == 4
