from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from src.models.chunk_asset import ChunkAsset
from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.services.doc_chunk.content_md_store import persist_content_md
from src.services.knowledge.chunk_service import (
    ChunkConflictError,
    create_knowledge_chunk,
)
from src.services.knowledge.taxonomy_service import TaxonomyValidationError
from tests.helpers.chunk_payload import minimal_chunk_payload


def _seed_file_import(db_session, kb_id):
    row = FileImport(
        kb_id=kb_id,
        file_name="chunk-service.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path="/tmp/chunk-service.docx",
        file_purpose=FilePurpose.actual_bid,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(row)
    db_session.flush()
    return row


def _seed_document_tree(db_session, kb_id):
    file_import = _seed_file_import(db_session, kb_id)
    document = Document(
        kb_id=kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        source_usage=DocumentSourceUsage.knowledge_extract,
        document_name="chunk-service.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()

    parent_id = uuid4()
    child_id = uuid4()
    parent = DocumentTreeNode(
        node_id=parent_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=None,
        node_type=DocumentTreeNodeType.heading,
        title="第一章 总则",
        level=1,
        sort_order=0,
        tree_version=1,
    )
    child = DocumentTreeNode(
        node_id=child_id,
        kb_id=kb_id,
        document_id=document.document_id,
        parent_id=parent_id,
        node_type=DocumentTreeNodeType.heading,
        title="1.1 范围",
        level=2,
        sort_order=1,
        tree_version=1,
    )
    db_session.add_all([parent, child])
    db_session.commit()
    return document, parent, child


def test_create_chunk_initial_version(db_session, seeded_kb, tmp_path):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    source = tmp_path / "content.md"
    source.write_text("# 第一章 总则\n\n正文内容\n", encoding="utf-8")
    persisted = persist_content_md(document_id=document.document_id, source_path=Path(source))
    assert persisted is not None

    asset = ChunkAsset(
        id=1,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        asset_type="image",
        char_start=3,
        char_end=8,
    )
    db_session.add(asset)
    db_session.commit()

    chunk = create_knowledge_chunk(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=minimal_chunk_payload(),
        doc_id=document.document_id,
        primary_node_id=parent.node_id,
    )

    assert chunk.version == "1.0"
    assert chunk.is_latest is True
    assert chunk.previous_version_id is None
    assert chunk.content_hash == hashlib.sha256("正文内容 A B C".encode("utf-8")).hexdigest()
    assert chunk.token_count == 4
    assert chunk.children_count == 1
    assert chunk.has_children is True
    assert chunk.block_type_code == "product_solution"
    assert chunk.application_type_code == "preferred_reference"
    assert chunk.business_line_codes == ["general"]
    assert chunk.catalog_path == [
        {"node_id": str(parent.node_id), "title": "第一章 总则", "level": 1}
    ]
    db_session.refresh(asset)
    assert asset.chunk_id == chunk.id


def test_create_chunk_conflict_without_force(db_session, seeded_kb, tmp_path):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    source = tmp_path / "content.md"
    source.write_text("# 第一章 总则\n\n正文内容\n", encoding="utf-8")
    persisted = persist_content_md(document_id=document.document_id, source_path=Path(source))
    assert persisted is not None

    create_knowledge_chunk(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=minimal_chunk_payload(),
        doc_id=document.document_id,
        primary_node_id=parent.node_id,
    )

    with pytest.raises(ChunkConflictError) as exc_info:
        create_knowledge_chunk(
            db_session,
            kb_id=seeded_kb.kb_id,
            payload=minimal_chunk_payload(),
            doc_id=document.document_id,
            primary_node_id=parent.node_id,
            force=False,
        )
    assert exc_info.value.existing_id is not None
    assert exc_info.value.existing_version == "1.0"


def test_create_chunk_force_bumps_version(db_session, seeded_kb, tmp_path):
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    source = tmp_path / "content.md"
    source.write_text("# 第一章 总则\n\n正文内容\n", encoding="utf-8")
    persisted = persist_content_md(document_id=document.document_id, source_path=Path(source))
    assert persisted is not None

    first = create_knowledge_chunk(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=minimal_chunk_payload(content="首版内容"),
        doc_id=document.document_id,
        primary_node_id=parent.node_id,
    )
    second = create_knowledge_chunk(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=minimal_chunk_payload(content="覆盖内容"),
        doc_id=document.document_id,
        primary_node_id=parent.node_id,
        force=True,
    )

    assert second.version == "1.1"
    assert second.previous_version_id == first.id
    db_session.refresh(first)
    assert first.is_latest is False


def test_create_chunk_auto_sets_char_range_and_certificate_fields(
    db_session, seeded_kb, tmp_path
):
    from src.models.knowledge_chunk import KnowledgeChunk

    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    source = tmp_path / "content.md"
    source.write_text("# 第一章 总则\n\n## 1.1\n\n资质正文XYZ\n", encoding="utf-8")
    persisted = persist_content_md(document_id=document.document_id, source_path=Path(source))
    assert persisted is not None

    chunk = create_knowledge_chunk(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=minimal_chunk_payload(
            content="资质正文XYZ",
            certificate_number="CERT-001, CERT-002",
            certificate_date="2024-01-01,2025-01-01",
            expire_date="2025-06-01",
        ),
        doc_id=document.document_id,
        primary_node_id=parent.node_id,
    )
    row = db_session.get(KnowledgeChunk, chunk.id)
    assert row is not None
    assert row.char_start is not None
    assert row.char_end is not None
    assert row.certificate_number == "CERT-001,CERT-002"
    assert row.certificate_date == "2024-01-01,2025-01-01"
    assert not hasattr(row, "page_start")
    assert row.expire_date is not None
    assert row.expire_date.isoformat() == "2025-06-01"


def test_create_chunk_rejects_invalid_block_type(db_session, seeded_kb, seeded_taxonomy, tmp_path):
    _ = seeded_taxonomy
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    source = tmp_path / "content.md"
    source.write_text("# 第一章 总则\n\n正文内容\n", encoding="utf-8")
    persisted = persist_content_md(document_id=document.document_id, source_path=Path(source))
    assert persisted is not None

    with pytest.raises(TaxonomyValidationError):
        create_knowledge_chunk(
            db_session,
            kb_id=seeded_kb.kb_id,
            payload=minimal_chunk_payload(block_type_code="bogus"),
            doc_id=document.document_id,
            primary_node_id=parent.node_id,
        )
