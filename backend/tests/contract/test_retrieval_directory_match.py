from uuid import uuid4

from src.models.bid_outline import BidOutline, BidOutlineExtractStrategy, BidOutlineStatus, BidOutlineType
from src.models.bid_outline_node import BidOutlineNode, BidOutlineNodeStatus
from src.models.chapter_pattern import ChapterPattern, ChapterPatternStatus
from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus, RetrievalObjectType
from src.models.retrieval_trace import RetrievalIntent, RetrievalTrace
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.models.template_library import TemplateLibrary, TemplateLibraryStatus, TemplateLibraryType


def _seed_file_import(db_session, kb_id, *, name: str, purpose: FilePurpose) -> FileImport:
    item = FileImport(
        kb_id=kb_id,
        file_name=name,
        file_type=FileType.docx,
        file_size=1024,
        storage_path=f"/tmp/{name}",
        file_purpose=purpose,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(item)
    db_session.flush()
    return item


def test_directory_match_returns_match_and_missing_chapters(client, db_session, seeded_kb):
    category_id = str(uuid4())
    actual_import = _seed_file_import(
        db_session, seeded_kb.kb_id, name="actual.docx", purpose=FilePurpose.actual_bid
    )
    template_import = _seed_file_import(
        db_session, seeded_kb.kb_id, name="template.docx", purpose=FilePurpose.template_file
    )

    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=actual_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        source_usage=DocumentSourceUsage.knowledge_extract,
        product_category_ids=[category_id],
        document_name="示例招标文件",
        parse_status=DocumentParseStatus.ready,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()

    outline = BidOutline(
        kb_id=seeded_kb.kb_id,
        source_doc_id=document.document_id,
        import_id=actual_import.import_id,
        outline_name="示例目录",
        outline_type=BidOutlineType.actual_bid,
        product_category_ids=[category_id],
        status=BidOutlineStatus.confirmed,
        extract_strategy=BidOutlineExtractStrategy.toc,
        created_by="tester",
    )
    db_session.add(outline)
    db_session.flush()

    outline_node = BidOutlineNode(
        kb_id=seeded_kb.kb_id,
        bid_outline_id=outline.bid_outline_id,
        parent_id=None,
        title="1. 技术方案",
        level=1,
        sort_order=0,
        product_category_ids=[category_id],
        status=BidOutlineNodeStatus.confirmed,
        needs_manual_review=False,
    )
    db_session.add(outline_node)

    library = TemplateLibrary(
        kb_id=seeded_kb.kb_id,
        library_name="模板库",
        library_type=TemplateLibraryType.technical,
        status=TemplateLibraryStatus.published,
        created_by="tester",
    )
    db_session.add(library)
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        template_library_id=library.template_library_id,
        source_import_id=template_import.import_id,
        template_name="标准技术模板",
        template_type=TemplateType.technical_bid,
        product_category_ids=[category_id],
        status=TemplateStatus.published,
        created_by="tester",
    )
    db_session.add(template)
    db_session.flush()

    template_chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="技术方案",
        level=1,
        sort_order=0,
        product_category_ids=[category_id],
        status=TemplateChapterStatus.published,
    )
    db_session.add(template_chapter)

    pattern = ChapterPattern(
        kb_id=seeded_kb.kb_id,
        pattern_name="售后服务",
        product_category_ids=[category_id],
        frequency=6,
        status=ChapterPatternStatus.confirmed,
    )
    db_session.add(pattern)

    ku_index = RetrievalIndexEntry(
        kb_id=seeded_kb.kb_id,
        object_type=RetrievalObjectType.ku,
        object_id=outline_node.outline_node_id,
        title="技术方案最佳实践",
        content_text="内容",
        product_category_ids=[category_id],
        status=RetrievalIndexStatus.published,
    )
    db_session.add(ku_index)
    db_session.commit()

    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/directory-match",
        json={
            "product_category_ids": [category_id],
            "outline_nodes": [{"title": "1. 技术方案", "level": 1, "sort_order": 0}],
            "retrieval_options": {"top_k": 10},
            "return_options": {"include_trace": True, "include_score_detail": True},
        },
        headers={"X-Operator-Id": "tester"},
    )

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["trace_id"]
    assert str(template_chapter.template_chapter_id) in payload["directory_match"][
        "matched_template_chapter_ids"
    ]
    assert str(outline_node.outline_node_id) in payload["directory_match"]["matched_outline_ids"]
    assert payload["directory_match"]["missing_chapters"][0]["pattern_id"] == str(pattern.pattern_id)

    trace = (
        db_session.query(RetrievalTrace)
        .filter(RetrievalTrace.kb_id == seeded_kb.kb_id)
        .order_by(RetrievalTrace.created_at.desc())
        .first()
    )
    assert trace is not None
    assert trace.intent == RetrievalIntent.directory_match
