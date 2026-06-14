from datetime import datetime, timezone

from src.models.candidate_knowledge import (
    CandidateKnowledge,
    CandidateKnowledgeStatus,
    CandidateKnowledgeType,
)
from src.models.candidate_knowledge_stub import (
    CandidateKnowledgeStub,
    CandidateKnowledgeStubStatus,
)
from src.models.document import Document, DocumentParseStatus, DocumentSourceType
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus


def _seed_document_candidate(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="actual-bid.docx",
        file_type=FileType.docx,
        file_size=128,
        storage_path=f"{seeded_kb.kb_id}/actual-bid.docx",
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
        document_name="实际标书A",
        parse_status=DocumentParseStatus.ready,
        created_by="admin",
    )
    db_session.add(document)
    db_session.flush()

    node = DocumentTreeNode(
        kb_id=seeded_kb.kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="3.2 云平台架构",
        level=2,
        sort_order=1,
        tree_version=1,
    )
    db_session.add(node)
    db_session.flush()

    candidate = CandidateKnowledge(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_doc_id=document.document_id,
        source_node_id=node.node_id,
        candidate_type=CandidateKnowledgeType.ku,
        title="云平台架构设计",
        content="完整正文内容",
        summary="文档侧候选",
        suggested_knowledge_type="solution",
        suggested_product_category_ids=[],
        confidence_score=0.88,
        status=CandidateKnowledgeStatus.pending,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(candidate)
    db_session.commit()
    return candidate, file_import, document, node


def _seed_template_candidate(db_session, seeded_kb):
    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="template-source.docx",
        file_type=FileType.docx,
        file_size=256,
        storage_path=f"{seeded_kb.kb_id}/template-source.docx",
        status=FileImportStatus.completed,
        file_purpose=FilePurpose.template_file,
        created_by="admin",
    )
    db_session.add(file_import)
    db_session.flush()

    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=file_import.import_id,
        template_name="政务云模板",
        template_type=TemplateType.technical_bid,
        status=TemplateStatus.published,
        created_by="admin",
    )
    db_session.add(template)
    db_session.flush()

    chapter = TemplateChapter(
        kb_id=seeded_kb.kb_id,
        template_id=template.template_id,
        parent_id=None,
        title="总体方案",
        level=1,
        sort_order=1,
        status=TemplateChapterStatus.published,
    )
    db_session.add(chapter)
    db_session.flush()

    stub = CandidateKnowledgeStub(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        template_id=template.template_id,
        template_chapter_id=chapter.template_chapter_id,
        material_id=None,
        candidate_type=CandidateKnowledgeType.wiki,
        title="模板-政策背景",
        summary="模板侧候选",
        content_preview="模板内容预览",
        product_category_ids=[],
        status=CandidateKnowledgeStubStatus.pending_confirm,
        classification_confidence=0.66,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(stub)
    db_session.commit()
    return stub, file_import, template, chapter


def test_list_candidates_aggregates_document_and_template(client, db_session, seeded_kb):
    doc_candidate, doc_import, document, node = _seed_document_candidate(db_session, seeded_kb)
    template_stub, template_import, template, chapter = _seed_template_candidate(db_session, seeded_kb)

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 20
    ids = {row["candidate_id"] for row in payload["items"]}
    assert f"doc_{doc_candidate.candidate_id}" in ids
    assert f"tpl_{template_stub.stub_id}" in ids

    doc_row = next(item for item in payload["items"] if item["source_channel"] == "document")
    assert doc_row["import_id"] == str(doc_import.import_id)
    assert doc_row["source_doc_id"] == str(document.document_id)
    assert doc_row["source_node_id"] == str(node.node_id)
    assert doc_row["candidate_type"] == "ku"
    assert doc_row["status"] == "pending"
    assert doc_row["source_trace"]["file_name"] == "actual-bid.docx"
    assert doc_row["source_trace"]["document_name"] == "实际标书A"
    assert doc_row["source_trace"]["node_title"] == "3.2 云平台架构"

    tpl_row = next(item for item in payload["items"] if item["source_channel"] == "template")
    assert tpl_row["import_id"] == str(template_import.import_id)
    assert tpl_row["source_doc_id"] is None
    assert tpl_row["source_node_id"] is None
    assert tpl_row["candidate_type"] == "wiki"
    assert tpl_row["status"] == "pending"
    assert tpl_row["source_trace"]["file_name"] == "template-source.docx"
    assert tpl_row["source_trace"]["template_name"] == "政务云模板"
    assert tpl_row["source_trace"]["chapter_title"] == "总体方案"


def test_list_candidates_filters_and_pagination(client, db_session, seeded_kb):
    doc_candidate, doc_import, document, _ = _seed_document_candidate(db_session, seeded_kb)
    _seed_template_candidate(db_session, seeded_kb)

    doc_only = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"source_channel": "document", "source_doc_id": str(document.document_id)},
        headers={"X-Operator-Id": "admin"},
    )
    assert doc_only.status_code == 200
    doc_data = doc_only.json()["data"]
    assert doc_data["total"] == 1
    assert doc_data["items"][0]["candidate_id"] == f"doc_{doc_candidate.candidate_id}"

    tpl_only = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"source_channel": "template", "candidate_type": "wiki"},
        headers={"X-Operator-Id": "admin"},
    )
    assert tpl_only.status_code == 200
    tpl_data = tpl_only.json()["data"]
    assert tpl_data["total"] == 1
    assert tpl_data["items"][0]["source_channel"] == "template"

    paged = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"page": 2, "page_size": 1},
        headers={"X-Operator-Id": "admin"},
    )
    assert paged.status_code == 200
    page_data = paged.json()["data"]
    assert page_data["total"] == 2
    assert page_data["page"] == 2
    assert page_data["page_size"] == 1
    assert len(page_data["items"]) == 1

    import_filtered = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"import_id": str(doc_import.import_id)},
        headers={"X-Operator-Id": "admin"},
    )
    assert import_filtered.status_code == 200
    import_data = import_filtered.json()["data"]
    assert import_data["total"] == 1
    assert import_data["items"][0]["candidate_id"] == f"doc_{doc_candidate.candidate_id}"


def test_get_candidate_detail_supports_prefixed_id(client, db_session, seeded_kb):
    doc_candidate, doc_import, document, node = _seed_document_candidate(db_session, seeded_kb)
    template_stub, template_import, template, chapter = _seed_template_candidate(db_session, seeded_kb)

    doc_detail = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/doc_{doc_candidate.candidate_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert doc_detail.status_code == 200
    doc_data = doc_detail.json()["data"]
    assert doc_data["candidate_id"] == f"doc_{doc_candidate.candidate_id}"
    assert doc_data["source_channel"] == "document"
    assert doc_data["content"] == "完整正文内容"
    assert doc_data["source_trace"]["import_id"] == str(doc_import.import_id)
    assert doc_data["source_trace"]["source_doc_id"] == str(document.document_id)
    assert doc_data["source_trace"]["source_node_id"] == str(node.node_id)

    tpl_detail = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/tpl_{template_stub.stub_id}",
        headers={"X-Operator-Id": "admin"},
    )
    assert tpl_detail.status_code == 200
    tpl_data = tpl_detail.json()["data"]
    assert tpl_data["candidate_id"] == f"tpl_{template_stub.stub_id}"
    assert tpl_data["source_channel"] == "template"
    assert tpl_data["content"] == "模板内容预览"
    assert tpl_data["source_trace"]["import_id"] == str(template_import.import_id)
    assert tpl_data["source_trace"]["template_id"] == str(template.template_id)
    assert tpl_data["source_trace"]["template_chapter_id"] == str(chapter.template_chapter_id)


def test_get_candidate_detail_not_found(client, seeded_kb):
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/doc_00000000-0000-0000-0000-000000000001",
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "CANDIDATE_NOT_FOUND"


def test_list_candidates_includes_content_excerpt(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"source_channel": "document", "status": "pending"},
    )
    assert resp.status_code == 200
    item = resp.json()["data"]["items"][0]
    assert item["content_excerpt"] == "完整正文内容"


def test_list_candidates_pending_confirm_does_not_500(client, db_session, seeded_kb):
    _seed_document_candidate(db_session, seeded_kb)
    _seed_template_candidate(db_session, seeded_kb)

    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"status": "pending_confirm"},
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["source_channel"] == "template"
