from uuid import uuid4

import pytest

from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeStatus, CandidateKnowledgeType
from src.models.document import Document, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus
from src.services.file_import_purge_service import (
    FileImportPurgeServiceError,
    check_purge_impact,
    purge_file_import,
)


def _seed_import(db_session, kb_id):
    imp = FileImport(
        kb_id=kb_id,
        file_name="test.docx",
        file_type=FileType.docx,
        file_size=100,
        storage_path="/tmp/test.docx",
        status=FileImportStatus.completed,
        file_purpose=FilePurpose.actual_bid,
        created_by="tester",
    )
    db_session.add(imp)
    db_session.flush()
    return imp


def test_check_purge_impact_counts_published_ku(db_session, seeded_kb):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="test.docx",
        created_by="tester",
    )
    db_session.add(doc)
    db_session.flush()
    node = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=doc.document_id,
        node_type=DocumentTreeNodeType.heading,
        title="section",
        level=1,
        sort_order=0,
        tree_version=1,
    )
    db_session.add(node)
    db_session.flush()
    db_session.add(
        KnowledgeUnit(
            kb_id=seeded_kb.kb_id,
            title="KU",
            content="body",
            knowledge_type="solution",
            product_category_ids=[],
            import_id=imp.import_id,
            candidate_id=uuid4(),
            published_by="tester",
            status=KnowledgeUnitStatus.published,
            source_doc_id=doc.document_id,
        )
    )
    db_session.add(
        CandidateKnowledge(
            kb_id=seeded_kb.kb_id,
            import_id=imp.import_id,
            source_doc_id=doc.document_id,
            source_node_id=node.node_id,
            candidate_type=CandidateKnowledgeType.ku,
            title="cand",
            content="c",
            status=CandidateKnowledgeStatus.pending,
        )
    )
    db_session.commit()

    report = check_purge_impact(db_session, kb_id=seeded_kb.kb_id, import_id=imp.import_id)
    assert report.has_published_assets is True
    assert report.published_counts["ku"] == 1
    assert report.published_total == 1
    assert report.intermediate_counts["candidate_knowledges"] == 1
    assert report.intermediate_counts["documents"] == 1


def test_purge_without_published_soft_deletes_import(db_session, seeded_kb):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="test.docx",
        created_by="tester",
    )
    db_session.add(doc)
    db_session.commit()

    summary = purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        operator_id="tester",
        trace_id=None,
        deprecate_published=False,
    )
    db_session.commit()

    refreshed = db_session.get(FileImport, imp.import_id)
    assert refreshed is not None
    assert refreshed.status == FileImportStatus.deleted
    assert summary.deleted_counts.get("documents") == 1
    assert db_session.query(Document).filter(Document.import_id == imp.import_id).count() == 0


def test_purge_with_published_ku_raises_without_flag(db_session, seeded_kb):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    db_session.add(
        KnowledgeUnit(
            kb_id=seeded_kb.kb_id,
            title="KU",
            content="body",
            knowledge_type="solution",
            product_category_ids=[],
            import_id=imp.import_id,
            candidate_id=uuid4(),
            published_by="tester",
            status=KnowledgeUnitStatus.published,
        )
    )
    db_session.commit()

    with pytest.raises(FileImportPurgeServiceError) as exc:
        purge_file_import(
            db_session,
            kb_id=seeded_kb.kb_id,
            import_id=imp.import_id,
            operator_id="tester",
            trace_id=None,
            deprecate_published=False,
        )
    assert exc.value.code == "PUBLISHED_ASSETS_EXIST"
    assert exc.value.status_code == 409


def test_purge_with_published_ku_deprecates_when_confirmed(db_session, seeded_kb):
    imp = _seed_import(db_session, seeded_kb.kb_id)
    ku = KnowledgeUnit(
        kb_id=seeded_kb.kb_id,
        title="KU",
        content="body",
        knowledge_type="solution",
        product_category_ids=[],
        import_id=imp.import_id,
        candidate_id=uuid4(),
        published_by="tester",
        status=KnowledgeUnitStatus.published,
    )
    db_session.add(ku)
    db_session.commit()

    summary = purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=imp.import_id,
        operator_id="tester",
        trace_id=None,
        deprecate_published=True,
    )
    db_session.commit()
    db_session.refresh(ku)

    assert ku.status == KnowledgeUnitStatus.deprecated
    assert ku.deprecated_at is not None
    assert summary.deprecated_counts.get("ku") == 1
    assert db_session.get(FileImport, imp.import_id).status == FileImportStatus.deleted
