from src.models.chapter_taxonomy import ChapterTaxonomy, CategoryStatus
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.services.candidate_generate_service import generate_for_document
from src.services.content_blocks import parse_content


def test_generate_for_document_uses_section_content(db_session, seeded_kb):
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
        content_preview="技术方案",
        chapter_taxonomy_id=taxonomy.taxonomy_id,
        tree_version=1,
    )
    paragraph = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        node_type=DocumentTreeNodeType.paragraph,
        sort_order=1,
        content_preview="章节正文",
        tree_version=1,
    )
    db_session.add_all([heading, paragraph])
    db_session.commit()

    created = generate_for_document(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        document_id=document.document_id,
    )
    assert len(created) == 1
    doc = parse_content(created[0].content)
    assert any(b.get("text") == "章节正文" for b in doc.blocks)
