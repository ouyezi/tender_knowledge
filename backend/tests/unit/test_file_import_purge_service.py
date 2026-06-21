from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.knowledge_chunk import KnowledgeChunk
from src.models.knowledge_blueprint import KnowledgeBlueprint
from src.services.file_import_purge_service import check_purge_impact, purge_file_import
from src.services.knowledge.blueprint_service import create_blueprint


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_import_with_chunk(db_session, seeded_kb):
    import_id = uuid4()
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="a.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/a.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        created_by="admin",
    )
    db_session.add(imp)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="a.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(doc)
    db_session.flush()
    db_session.add(
        KnowledgeChunk(
            id=1,
            kb_id=seeded_kb.kb_id,
            knowledge_code="K-001",
            version="1.0",
            title="t",
            content="c",
            knowledge_type="fact",
            doc_id=doc.document_id,
            source_type="bid",
            catalog_path=[],
            primary_node_id=str(uuid4()),
            category="technical",
            tags=[],
            products=[],
            industries=[],
            customer_types=[],
            regions=[],
            content_hash="abc123",
            token_count=1,
        )
    )
    db_session.commit()
    return import_id, doc


def test_check_purge_impact_counts_knowledge_chunks(db_session, seeded_kb):
    import_id, _doc = _seed_import_with_chunk(db_session, seeded_kb)

    report = check_purge_impact(db_session, kb_id=seeded_kb.kb_id, import_id=import_id)
    assert report.intermediate_counts["knowledge_chunks"] >= 1
    assert report.has_published_assets is False


def test_purge_file_import_hard_deletes_row(db_session, seeded_kb):
    import_id = uuid4()
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="b.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/b.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        created_by="admin",
    )
    db_session.add(imp)
    db_session.commit()

    summary = purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        operator_id="admin",
        trace_id=None,
    )
    db_session.commit()

    assert summary.status == "deleted"
    assert db_session.get(FileImport, import_id) is None
    assert summary.deleted_counts.get("file_imports") == 1


def test_purge_file_import_deletes_knowledge_chunks(db_session, seeded_kb):
    import_id, doc = _seed_import_with_chunk(db_session, seeded_kb)
    doc_id = doc.document_id

    purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        operator_id="admin",
        trace_id=None,
    )
    db_session.commit()

    assert db_session.query(KnowledgeChunk).filter(KnowledgeChunk.doc_id == doc_id).count() == 0


def test_purge_deletes_blueprints_for_document(db_session, seeded_kb):
    import_id, doc = _seed_import_with_chunk(db_session, seeded_kb)
    doc_id = doc.document_id
    create_blueprint(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={
            "name": "蓝图-待删除",
            "description": "purge-test",
            "source_doc_id": doc_id,
            "source_node_id": uuid4(),
            "source_chapter_title": "第一章",
            "product_tags": ["prod-a"],
            "industry_tags": ["ind-a"],
            "scenario_tags": ["scene-a"],
            "applicable_project_type": ["type-a"],
            "related_regulations": ["reg-a"],
            "overall_strategy": "先总后分",
            "common_mistakes": "避免空泛描述",
            "template_style": "formal",
            "usual_page_range": "10-20",
            "status": "active",
            "nodes": [
                {
                    "node_title": "章节一",
                    "node_level": 1,
                    "node_order": 1,
                    "importance_level": "required",
                    "children": [],
                }
            ],
        },
    )
    db_session.commit()

    purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        operator_id="admin",
        trace_id=None,
    )
    db_session.commit()

    assert (
        db_session.query(KnowledgeBlueprint)
        .filter(KnowledgeBlueprint.source_doc_id == doc_id)
        .count()
        == 0
    )


def test_purge_file_import_deletes_parse_task_before_document(db_session, seeded_kb):
    import_id = uuid4()
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="parse-task.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/parse-task.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        created_by="admin",
    )
    db_session.add(imp)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="parse-task.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(doc)
    db_session.flush()
    parent_node_id = uuid4()
    child_node_id = uuid4()
    db_session.add_all(
        [
            DocumentTreeNode(
                node_id=parent_node_id,
                kb_id=seeded_kb.kb_id,
                document_id=doc.document_id,
                node_type=DocumentTreeNodeType.heading,
                title="Root",
                sort_order=0,
                tree_version=1,
            ),
            DocumentTreeNode(
                node_id=child_node_id,
                kb_id=seeded_kb.kb_id,
                document_id=doc.document_id,
                parent_id=parent_node_id,
                node_type=DocumentTreeNodeType.paragraph,
                title="Child",
                sort_order=1,
                tree_version=1,
            ),
            ActualBidParseTask(
                kb_id=seeded_kb.kb_id,
                import_id=import_id,
                document_id=doc.document_id,
                status=ActualBidParseTaskStatus.ready,
                created_by="admin",
            ),
        ]
    )
    db_session.commit()
    doc_id = doc.document_id

    purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        operator_id="admin",
        trace_id=None,
    )
    db_session.commit()

    assert db_session.get(FileImport, import_id) is None
    assert db_session.query(Document).filter(Document.import_id == import_id).count() == 0
    assert (
        db_session.query(ActualBidParseTask)
        .filter(ActualBidParseTask.import_id == import_id)
        .count()
        == 0
    )
    assert (
        db_session.query(DocumentTreeNode)
        .filter(DocumentTreeNode.document_id == doc_id)
        .count()
        == 0
    )


def test_purge_file_import_writes_delete_audit_log(db_session, seeded_kb):
    import_id = uuid4()
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="audited.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/audited.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        created_by="admin",
    )
    db_session.add(imp)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="audited.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(doc)
    db_session.commit()

    purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        operator_id="admin",
        trace_id=None,
    )
    db_session.commit()

    from src.models.import_audit_log import ImportAuditAction, ImportAuditLog

    row = (
        db_session.query(ImportAuditLog)
        .filter(
            ImportAuditLog.kb_id == seeded_kb.kb_id,
            ImportAuditLog.action == ImportAuditAction.delete,
        )
        .order_by(ImportAuditLog.created_at.desc())
        .first()
    )
    assert row is not None
    assert row.payload_summary == {"file_name": "audited.docx"}


def test_purge_file_import_removes_storage_dirs(db_session, seeded_kb, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "uploads"))
    import_id = uuid4()
    imp = FileImport(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        file_name="c.docx",
        file_type=FileType.docx,
        file_size=1,
        storage_path="x/c.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        created_by="admin",
    )
    db_session.add(imp)
    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="c.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(doc)
    db_session.commit()

    storage_root = tmp_path / "uploads"
    import_dir = storage_root / str(seeded_kb.kb_id) / str(import_id)
    import_dir.mkdir(parents=True)
    (import_dir / "upload.docx").write_bytes(b"x")
    doc_dir = storage_root / "documents" / str(doc.document_id)
    doc_dir.mkdir(parents=True)
    (doc_dir / "content.md").write_text("# hi", encoding="utf-8")
    workspace_dir = storage_root / "doc_chunk_workspaces" / str(seeded_kb.kb_id) / str(import_id)
    workspace_dir.mkdir(parents=True)

    purge_file_import(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=import_id,
        operator_id="admin",
        trace_id=None,
    )
    db_session.commit()

    assert not import_dir.exists()
    assert not doc_dir.exists()
    assert not workspace_dir.exists()
