from dataclasses import dataclass

from src.models.bid_outline import BidOutlineExtractStrategy
from src.models.bid_outline_node import BidOutlineNode
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.bid_outline_extract_service import persist_outline


@dataclass
class _TocEntry:
    temp_id: str
    parent_temp_id: str | None
    title: str
    level: int
    sort_order: int


def test_persist_outline_maps_source_node_id(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="投标文件.docx",
        file_type=FileType.docx,
        file_size=123,
        hash_status=HashStatus.computed,
        file_hash="abc123",
        storage_path="imports/demo.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.confirmed,
        created_by="tester",
    )
    db_session.add(file_import)
    db_session.flush()

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="投标文件.docx",
        parse_status=DocumentParseStatus.ready,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()

    heading_node = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="1 技术方案",
        level=1,
        sort_order=0,
        content_ref=None,
        content_preview=None,
        chapter_taxonomy_id=None,
        product_category_ids=[],
        is_outline_node=True,
        candidate_template_chapter_id=None,
        candidate_pattern_id=None,
        needs_manual_review=False,
        tree_version=1,
    )
    db_session.add(heading_node)
    db_session.flush()

    result = persist_outline(
        db_session,
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        document_id=document.document_id,
        outline_name="投标目录",
        toc_entries=[_TocEntry("h1", None, "1 技术方案", 1, 0)],
        source_node_by_temp_id={"h1": heading_node.node_id},
        created_by="tester",
        extract_strategy=BidOutlineExtractStrategy.heading_heuristic.value,
    )
    db_session.commit()

    outline = result.bid_outline
    outline_nodes = (
        db_session.query(BidOutlineNode)
        .filter(BidOutlineNode.bid_outline_id == outline.bid_outline_id)
        .all()
    )
    assert outline.bid_outline_id is not None
    assert outline.extract_strategy == BidOutlineExtractStrategy.heading_heuristic
    assert len(outline_nodes) == 1
    assert outline_nodes[0].source_node_id == heading_node.node_id
