import time
from uuid import uuid4

from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.models.retrieval_index_entry import RetrievalIndexEntry, RetrievalIndexStatus, RetrievalObjectType
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_chapter import TemplateChapter, TemplateChapterStatus


def _seed_import(db_session, kb_id, *, name: str) -> FileImport:
    row = FileImport(
        kb_id=kb_id,
        file_name=name,
        file_type=FileType.docx,
        file_size=1024,
        storage_path=f"/tmp/{name}",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_module_suggestion_completes_within_reasonable_time(client, db_session, seeded_kb):
    category_id = str(uuid4())
    import_row = _seed_import(db_session, seeded_kb.kb_id, name="template-performance.docx")

    template = Template(
        kb_id=seeded_kb.kb_id,
        source_import_id=import_row.import_id,
        template_name="性能测试模板",
        template_type=TemplateType.technical_bid,
        product_category_ids=[category_id],
        status=TemplateStatus.published,
        created_by="tester",
    )
    db_session.add(template)
    db_session.flush()

    for idx in range(1, 61):
        db_session.add(
            TemplateChapter(
                kb_id=seeded_kb.kb_id,
                template_id=template.template_id,
                parent_id=None,
                title=f"{idx}. 技术章节 {idx}",
                level=1,
                sort_order=idx,
                product_category_ids=[category_id],
                status=TemplateChapterStatus.published,
            )
        )

    for idx in range(1, 151):
        db_session.add(
            RetrievalIndexEntry(
                kb_id=seeded_kb.kb_id,
                object_type=RetrievalObjectType.ku,
                object_id=uuid4(),
                title=f"知识条目 {idx}",
                content_text=f"技术方案内容 {idx}",
                product_category_ids=[category_id],
                status=RetrievalIndexStatus.published,
            )
        )
    db_session.commit()

    outline_nodes = [
        {"title": f"{idx}. 技术章节 {idx}", "level": 1, "sort_order": idx}
        for idx in range(1, 21)
    ]

    started_at = time.perf_counter()
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions",
        json={
            "product_category_ids": [category_id],
            "outline_nodes": outline_nodes,
            "retrieval_options": {"top_k": 20},
            "return_options": {"include_trace": True, "include_score_detail": True},
        },
        headers={"X-Operator-Id": "tester"},
    )
    elapsed_s = time.perf_counter() - started_at

    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["trace_id"]
    assert len(payload["module_suggestions"]) == len(outline_nodes)
    assert elapsed_s < 5.0
    assert payload["latency_ms"] < 5000
