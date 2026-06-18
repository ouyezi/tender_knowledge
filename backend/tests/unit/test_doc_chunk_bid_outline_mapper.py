from pathlib import Path
from uuid import uuid4

from src.models.bid_outline import BidOutlineExtractStrategy
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.services.doc_chunk.mappers.bid_outline import build_toc_entries, import_bid_outline, map_outline_strategy
from src.services.doc_chunk.mappers.document_tree import import_document_tree
from src.services.doc_chunk.mappers.media_assets import import_media_assets
from src.services.doc_chunk.types import ImportContext
from src.services.doc_chunk.workspace_loader import load_workspace

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def test_map_outline_strategy():
    assert map_outline_strategy("toc") == BidOutlineExtractStrategy.toc
    assert map_outline_strategy(None) == BidOutlineExtractStrategy.doc_chunk


def test_build_toc_entries_links_source_nodes(db_session, seeded_kb):
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
    import_media_assets(db_session, ctx=ctx, document=document, kb_id=seeded_kb.kb_id)
    import_document_tree(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        tree_payload=loaded.document_tree,
    )
    toc_entries, source_map = build_toc_entries(
        outline_payload=loaded.outline,
        linkage_payload=loaded.linkage,
        ctx=ctx,
    )
    assert len(toc_entries) == 2
    assert len(source_map) == 2


def test_import_bid_outline_persists_nodes(db_session, seeded_kb):
    loaded = load_workspace(FIXTURE_ROOT)
    import_id = uuid4()
    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="t.docx",
        parse_status=DocumentParseStatus.parsing,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()
    ctx = ImportContext(workspace_path=FIXTURE_ROOT)
    import_media_assets(db_session, ctx=ctx, document=document, kb_id=seeded_kb.kb_id)
    import_document_tree(
        db_session,
        ctx=ctx,
        document=document,
        kb_id=seeded_kb.kb_id,
        tree_payload=loaded.document_tree,
    )
    result = import_bid_outline(
        db_session,
        ctx=ctx,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        document_id=document.document_id,
        outline_name="t.docx",
        outline_payload=loaded.outline,
        linkage_payload=loaded.linkage,
    )
    assert result.node_count == 2
    assert result.bid_outline.extract_strategy == BidOutlineExtractStrategy.heading_heuristic
