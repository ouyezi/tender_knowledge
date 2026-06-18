"""Local-only regression: real doc_chunk pipeline + import_workspace on large bid."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from src.models.actual_bid_parse_task import ActualBidParseTask
from src.models.bid_outline_node import BidOutlineNode
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.document import Document, DocumentParseStatus
from src.models.document_tree_node import DocumentTreeNode
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.doc_chunk.import_service import import_workspace
from src.services.doc_chunk.pipeline_runner import run_doc_chunk_pipeline

CANBU = os.environ.get("DOC_CHUNK_CANBU_FIXTURE")
DINGXIN = os.environ.get("DOC_CHUNK_DINGXIN_FIXTURE")

FIXTURES = [p for p in (CANBU, DINGXIN) if p]
pytestmark = pytest.mark.skipif(not FIXTURES, reason="set DOC_CHUNK_CANBU_FIXTURE and/or DOC_CHUNK_DINGXIN_FIXTURE")


@pytest.mark.parametrize("fixture_path", FIXTURES)
def test_large_bid_pipeline_import_invariants(db_session, seeded_kb, tmp_path, fixture_path: str):
    src = Path(fixture_path)
    assert src.is_file(), f"missing fixture: {src}"

    import_id = uuid4()
    parse_task_id = uuid4()
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name=src.name,
        file_type=FileType.docx,
        file_size=src.stat().st_size,
        storage_path=f"{seeded_kb.kb_id}/{src.name}",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="admin",
        confirmed_by="admin",
    )
    task = ActualBidParseTask(
        parse_task_id=parse_task_id,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
    )
    db_session.add(file_import)
    db_session.add(task)
    db_session.commit()

    workspace = tmp_path / "ws"
    workspace.mkdir()
    run_doc_chunk_pipeline(src, workspace)

    result = import_workspace(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        document_id=None,
        parse_task_id=parse_task_id,
        workspace=workspace,
        file_import=file_import,
        task=task,
    )
    db_session.commit()

    document = db_session.get(Document, result.document_id)
    assert document is not None
    assert document.parse_status == DocumentParseStatus.ready

    outline_count = (
        db_session.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == result.bid_outline_id)
        .count()
    )
    candidate_count = (
        db_session.query(CandidateKnowledge)
        .filter(CandidateKnowledge.source_doc_id == result.document_id)
        .count()
    )
    tree_nodes = (
        db_session.query(DocumentTreeNode)
        .filter(DocumentTreeNode.document_id == result.document_id)
        .all()
    )
    tree_ids = [str(n.node_id) for n in tree_nodes]
    assert len(tree_ids) == len(set(tree_ids)), "document_tree node_id must be globally unique"

    assert outline_count > 0
    ratio = candidate_count / max(outline_count, 1)
    assert 0.8 <= ratio <= 1.2, f"candidate/outline ratio out of range: {ratio:.2f}"

    print(
        f"[{src.name}] outline={outline_count} candidates={candidate_count} "
        f"tree={len(tree_nodes)} ratio={ratio:.2f}"
    )
