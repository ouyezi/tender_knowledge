from uuid import uuid4

from src.services.knowledge.entry_content_service import compute_section_char_range


def test_compute_section_char_range_returns_slice_offsets(db_session, seeded_kb, monkeypatch):
    doc_id = uuid4()
    node_id = uuid4()
    content_md = "# 第一章\n\n## 1.1 资质\n\n正文ABC\n"

    monkeypatch.setattr(
        "src.services.knowledge.entry_content_service.load_content_md",
        lambda document_id: content_md if document_id == doc_id else None,
    )

    start, end = compute_section_char_range(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=doc_id,
        primary_node_id=node_id,
        content="正文ABC",
    )
    assert start is not None
    assert end is not None
    assert end - start == len("正文ABC")
