from uuid import uuid4

from src.models.bid_outline import BidOutline, BidOutlineExtractStrategy, BidOutlineStatus, BidOutlineType
from src.models.bid_outline_node import BidOutlineNode, BidOutlineNodeStatus
from src.models.chapter_pattern import ChapterPattern, ChapterPatternStatus
from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus, RetrievalObjectType
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus
from src.models.template_library import TemplateLibrary, TemplateLibraryStatus, TemplateLibraryType


def _seed_import(db_session, kb_id, *, name: str, purpose: FilePurpose) -> FileImport:
    row = FileImport(
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
    db_session.add(row)
    db_session.flush()
    return row


def test_epic5_quickstart_flow_directory_match_to_feedback_trace(client, db_session, seeded_kb):
    category_id = str(uuid4())

    actual_import = _seed_import(
        db_session, seeded_kb.kb_id, name="actual.docx", purpose=FilePurpose.actual_bid
    )
    template_import = _seed_import(
        db_session, seeded_kb.kb_id, name="template.docx", purpose=FilePurpose.template_file
    )

    doc = Document(
        kb_id=seeded_kb.kb_id,
        import_id=actual_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        source_usage=DocumentSourceUsage.knowledge_extract,
        product_category_ids=[category_id],
        document_name="示例投标文件",
        parse_status=DocumentParseStatus.ready,
        created_by="tester",
    )
    db_session.add(doc)
    db_session.flush()

    outline = BidOutline(
        kb_id=seeded_kb.kb_id,
        source_doc_id=doc.document_id,
        import_id=actual_import.import_id,
        outline_name="项目目录",
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

    template_lib = TemplateLibrary(
        kb_id=seeded_kb.kb_id,
        library_name="技术模板库",
        library_type=TemplateLibraryType.technical,
        status=TemplateLibraryStatus.published,
        created_by="tester",
    )
    db_session.add(template_lib)
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        template_library_id=template_lib.template_library_id,
        source_import_id=template_import.import_id,
        template_name="标准技术标模板",
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
        frequency=8,
        status=ChapterPatternStatus.confirmed,
    )
    db_session.add(pattern)

    db_session.add(
        RetrievalIndexEntry(
            kb_id=seeded_kb.kb_id,
            object_type=RetrievalObjectType.ku,
            object_id=uuid4(),
            title="技术方案经验库",
            content_text="覆盖架构设计与实施要点",
            product_category_ids=[category_id],
            status=RetrievalIndexStatus.published,
        )
    )
    db_session.commit()

    directory_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/directory-match",
        json={
            "product_category_ids": [category_id],
            "outline_nodes": [{"title": "1. 技术方案", "level": 1, "sort_order": 0}],
            "retrieval_options": {"top_k": 10},
            "return_options": {"include_trace": True, "include_score_detail": True},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert directory_resp.status_code == 200
    directory_payload = directory_resp.json()["data"]
    assert directory_payload["trace_id"]
    assert str(template_chapter.template_chapter_id) in directory_payload["directory_match"][
        "matched_template_chapter_ids"
    ]

    suggestion_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions",
        json={
            "product_category_ids": [category_id],
            "outline_nodes": [{"title": "1. 技术方案", "level": 1, "sort_order": 0}],
            "tender_requirement_context": {"score_points": ["实施可行性"], "rejection_clauses": []},
            "retrieval_options": {"top_k": 10},
            "return_options": {"include_trace": True, "include_score_detail": True},
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert suggestion_resp.status_code == 200
    suggestion_payload = suggestion_resp.json()["data"]
    assert suggestion_payload["trace_id"]
    assert len(suggestion_payload["module_suggestions"]) >= 1

    feedback_resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/feedback",
        json={
            "trace_id": suggestion_payload["trace_id"],
            "feedback_type": "useful",
            "object_type": "template_chapter",
            "object_id": str(template_chapter.template_chapter_id),
            "rank_position": 1,
            "expected_object_ids": [],
            "comment": "建议命中目录要求",
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert feedback_resp.status_code == 200
    feedback_payload = feedback_resp.json()["data"]
    assert feedback_payload["trace_id"] == suggestion_payload["trace_id"]

    trace_detail_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/traces/{suggestion_payload['trace_id']}",
        headers={"X-Operator-Id": "tester"},
    )
    assert trace_detail_resp.status_code == 200
    trace_detail = trace_detail_resp.json()["data"]
    assert trace_detail["intent"] == "module_suggestion"
    assert "request_snapshot" in trace_detail

    trace_list_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/retrieval/traces?intent=module_suggestion&page_size=20",
        headers={"X-Operator-Id": "tester"},
    )
    assert trace_list_resp.status_code == 200
    listed = trace_list_resp.json()["data"]["items"]
    assert any(item["trace_id"] == suggestion_payload["trace_id"] for item in listed)
