from pathlib import Path
from uuid import uuid4

import pytest

from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeType
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.services.doc_chunk.mappers.candidates import import_candidates
from src.services.doc_chunk.mappers.document_tree import import_document_tree
from src.services.doc_chunk.mappers.media_assets import import_media_assets
from src.services.doc_chunk.types import DocChunkImportError, ImportContext
from src.services.doc_chunk.workspace_loader import load_workspace

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "doc_chunk_workspace_minimal"


def _prepare_ctx(db_session, seeded_kb):
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
    return loaded, document, ctx


def test_import_candidates_skips_preface(db_session, seeded_kb):
    loaded, document, ctx = _prepare_ctx(db_session, seeded_kb)
    linkage = dict(loaded.linkage)
    linkage["entries"] = list(linkage["entries"]) + [
        {
            "outline_node_id": "n9",
            "document_tree_node_ids": ["t0001"],
            "chunk_ids": ["chunk-preface"],
            "primary_chunk_id": "chunk-preface",
        }
    ]
    chunks_index = dict(loaded.chunks_index)
    chunks_index["chunks"] = list(chunks_index["chunks"]) + [
        {
            "chunk_id": "chunk-preface",
            "title": "Preface",
            "path": "chunk-preface.json",
            "original_node_ids": ["n9"],
        }
    ]
    preface_path = FIXTURE_ROOT / "chunks" / "chunk-preface.json"
    preface_path.write_text(
        '{"schema_version":"1.0","chunk_id":"chunk-preface","title":"Preface","blocks":[],"original_node_ids":["n9"],"metadata":{}}',
        encoding="utf-8",
    )
    try:
        created = import_candidates(
            db_session,
            ctx=ctx,
            kb_id=seeded_kb.kb_id,
            import_id=document.import_id,
            document_id=document.document_id,
            parse_task_id=uuid4(),
            linkage_payload=linkage,
            chunks_index=chunks_index,
            warnings=[],
        )
        assert len(created) == 2
        assert all(c.title != "Preface" for c in created)
    finally:
        if preface_path.exists():
            preface_path.unlink()


def test_import_candidates_blocks_v1_content(db_session, seeded_kb):
    loaded, document, ctx = _prepare_ctx(db_session, seeded_kb)
    created = import_candidates(
        db_session,
        ctx=ctx,
        kb_id=seeded_kb.kb_id,
        import_id=document.import_id,
        document_id=document.document_id,
        parse_task_id=uuid4(),
        linkage_payload=loaded.linkage,
        chunks_index=loaded.chunks_index,
        warnings=[],
    )
    assert len(created) == 2
    assert "blocks_v1" in (created[0].content or "")
