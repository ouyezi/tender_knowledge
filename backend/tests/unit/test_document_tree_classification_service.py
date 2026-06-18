from src.models.chapter_taxonomy import ChapterTaxonomy, CategoryStatus
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.document_tree_classification_service import classify_heading_nodes_for_document


def test_classify_heading_nodes_assigns_taxonomy(db_session, seeded_kb):
    taxonomy = ChapterTaxonomy(
        kb_id=seeded_kb.kb_id,
        parent_id=None,
        standard_name="技术方案",
        taxonomy_code="technical_solution",
        status=CategoryStatus.active,
        path="",
        depth=0,
    )
    taxonomy.path = f"/{taxonomy.taxonomy_id}/"
    db_session.add(taxonomy)
    db_session.flush()

    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="bid.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path=f"{seeded_kb.kb_id}/bid.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="标书",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    heading = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        node_type=DocumentTreeNodeType.heading,
        title="技术方案",
        level=1,
        sort_order=0,
        content_preview="技术方案概述",
        tree_version=1,
    )
    db_session.add(heading)
    db_session.commit()

    summary = classify_heading_nodes_for_document(
        db_session,
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
    )
    db_session.refresh(heading)

    assert summary.heading_count == 1
    assert summary.taxonomy_assigned_count == 1
    assert heading.chapter_taxonomy_id == taxonomy.taxonomy_id


def test_classify_heading_nodes_rule_only_skips_llm(db_session, seeded_kb, monkeypatch):
    from src.services import chunk_classification_service

    llm_called = {"count": 0}

    def _fake_llm(*_args, **_kwargs):
        llm_called["count"] += 1
        return None

    monkeypatch.setattr(chunk_classification_service, "_llm_classify", _fake_llm)
    monkeypatch.setattr(chunk_classification_service, "is_llm_available", lambda: True)

    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="bid.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path=f"{seeded_kb.kb_id}/bid.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="标书",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    for sort_order in range(3):
        db_session.add(
            DocumentTreeNode(
                kb_id=seeded_kb.kb_id,
                document_id=document.document_id,
                node_type=DocumentTreeNodeType.heading,
                title=f"章节 {sort_order}",
                level=1,
                sort_order=sort_order,
                tree_version=1,
            )
        )
    db_session.commit()

    summary = classify_heading_nodes_for_document(
        db_session,
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        use_llm=False,
    )

    assert summary.heading_count == 3
    assert llm_called["count"] == 0
    assert summary.to_payload(use_llm=False)["mode"] == "rule_only"


def test_classify_then_generate_candidates(db_session, seeded_kb, monkeypatch):
    from src.models.candidate_knowledge import CandidateKnowledge
    from src.services import chapter_candidate_rules
    from src.services.candidate_generate_service import generate_for_document

    monkeypatch.setattr(
        chapter_candidate_rules,
        "_CACHE",
        {
            "default": {"candidate_type": "ignore", "suggested_knowledge_type": None},
            "rules": {"technical_solution": {"candidate_type": "ku", "suggested_knowledge_type": "solution"}},
        },
    )

    taxonomy = ChapterTaxonomy(
        kb_id=seeded_kb.kb_id,
        parent_id=None,
        standard_name="技术方案",
        taxonomy_code="technical_solution",
        status=CategoryStatus.active,
        path="",
        depth=0,
    )
    taxonomy.path = f"/{taxonomy.taxonomy_id}/"
    db_session.add(taxonomy)
    db_session.flush()

    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="bid.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path=f"{seeded_kb.kb_id}/bid.docx",
        status=FileImportStatus.confirmed,
        file_purpose=FilePurpose.actual_bid,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="标书",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    heading = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        node_type=DocumentTreeNodeType.heading,
        title="技术方案",
        level=1,
        sort_order=0,
        content_preview="技术方案概述",
        tree_version=1,
    )
    db_session.add(heading)
    db_session.commit()

    classify_heading_nodes_for_document(
        db_session,
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
    )
    created = generate_for_document(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        document_id=document.document_id,
    )
    db_session.commit()

    assert len(created) == 1
    assert db_session.query(CandidateKnowledge).count() == 1
