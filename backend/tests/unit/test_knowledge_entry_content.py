from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.chunk_asset import ChunkAsset
from src.models.document import Document, DocumentParseStatus, DocumentSourceType, DocumentSourceUsage
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.file_import import FileImport, FileImportStatus, FilePurpose, FileType, HashStatus
from src.models.knowledge_chunk import KnowledgeChunk
from src.services.doc_chunk.content_md_store import persist_content_md
from src.services.doc_chunk.outline_store import persist_outline, persist_outline_node_map
from src.services.doc_chunk.section_slice import PREFACE_NODE_ID
from src.services.knowledge.entry_content_service import get_document_tree, get_node_preview


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_outline_for_document(
    *,
    document_id,
    parent,
    content_md: str,
    storage_root,
    monkeypatch,
    child=None,
    extra_headings: list[tuple[str, str, str | None]] | None = None,
):
    """extra_headings: (outline_id, heading_marker, parent_outline_id)"""
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    parent_start = content_md.index("# 第一章")
    nodes = [
        {
            "node_id": "n1",
            "title": parent.title,
            "level": parent.level,
            "parent_id": None,
            "sort_order": parent.sort_order,
            "anchor": {"char_start": parent_start, "char_end": parent_start + 5},
        }
    ]
    mapping = {"n1": parent.node_id}
    next_sort = parent.sort_order + 1
    if child is not None:
        child_start = content_md.index("## 1.1")
        nodes.append(
            {
                "node_id": "n2",
                "title": child.title,
                "level": child.level,
                "parent_id": "n1",
                "sort_order": child.sort_order,
                "anchor": {"char_start": child_start, "char_end": child_start + 5},
            }
        )
        mapping["n2"] = child.node_id
        next_sort = max(next_sort, child.sort_order + 1)
    for outline_id, marker, parent_outline_id in extra_headings or []:
        section_start = content_md.index(marker)
        nodes.append(
            {
                "node_id": outline_id,
                "title": marker.lstrip("# ").strip(),
                "level": marker.count("#"),
                "parent_id": parent_outline_id,
                "sort_order": next_sort,
                "anchor": {"char_start": section_start, "char_end": section_start + 5},
            }
        )
        next_sort += 1
    persist_outline(
        document_id=document_id,
        outline_payload={"nodes": nodes},
    )
    persist_outline_node_map(
        document_id=document_id,
        outline_node_to_tree_id=mapping,
    )


def _seed_file_import(db_session, kb_id):
    row = FileImport(
        kb_id=kb_id,
        file_name="entry-content.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path="/tmp/entry-content.docx",
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
        document_name="entry-content.docx",
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


def test_get_node_preview_excludes_mispositioned_table_assets(db_session, seeded_kb, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    section_md = (
        "## 1.1 范围\n\n"
        "兹证明某某同志为我单位法定代表人。\n\n"
        "特此证明。\n"
    )
    foreign_table = "| 指标 | 2019 | 2020 |\n| --- | --- | --- |\n| 净资产 | 1% | 2% |"
    source = tmp_path / "content.md"
    source.write_text(
        "# 第一章 总则\n\n父节点内容。\n\n"
        f"{section_md}\n\n"
        "## 1.2 财务状况\n\n"
        f"{foreign_table}\n",
        encoding="utf-8",
    )
    persist_content_md(document_id=document.document_id, source_path=Path(source))
    _seed_outline_for_document(
        document_id=document.document_id,
        parent=parent,
        child=child,
        content_md=source.read_text(encoding="utf-8"),
        storage_root=tmp_path,
        monkeypatch=monkeypatch,
        extra_headings=[("n3", "## 1.2 财务状况", "n1")],
    )

    section_start = source.read_text(encoding="utf-8").index("## 1.1 范围")
    db_session.add(
        ChunkAsset(
            id=1,
            kb_id=seeded_kb.kb_id,
            doc_id=document.document_id,
            asset_type="table",
            char_start=section_start + 40,
            char_end=section_start + 500,
            raw_markdown=foreign_table,
        )
    )
    db_session.commit()

    preview = get_node_preview(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=child.node_id,
    )

    assert "| 指标 |" not in preview["content_md"]
    assert preview["content_type"] == "text"
    assert preview["assets"] == []


def test_get_node_preview_parent_includes_child_content(db_session, seeded_kb, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    source = tmp_path / "content.md"
    content_md = "# 第一章 总则\n\n父节点内容。\n\n## 1.1 范围\n\n子节点内容。\n"
    source.write_text(content_md, encoding="utf-8")
    persisted = persist_content_md(document_id=document.document_id, source_path=Path(source))
    assert persisted is not None
    _seed_outline_for_document(
        document_id=document.document_id,
        parent=parent,
        child=child,
        content_md=content_md,
        storage_root=tmp_path,
        monkeypatch=monkeypatch,
    )

    preview = get_node_preview(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=parent.node_id,
    )

    assert preview["title"] == "第一章 总则"
    assert "父节点内容" in preview["content_md"]
    assert "子节点内容" in preview["content_md"]
    assert preview["content_type"] == "text"
    assert preview["char_start"] is not None
    assert preview["char_end"] is not None
    assert preview["catalog_path"] == [
        {"node_id": str(parent.node_id), "title": "第一章 总则", "level": 1}
    ]


def test_get_document_tree_marks_ingested_from_latest_chunk(db_session, seeded_kb):
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    db_session.add(
        KnowledgeChunk(
            id=1,
            kb_id=seeded_kb.kb_id,
            knowledge_code=str(uuid4()),
            version="1.0",
            is_latest=True,
            title="child-ingested",
            content="test",
            knowledge_type="section",
            content_type="text",
            doc_id=document.document_id,
            block_type_code="product_solution",
            application_type_code="preferred_reference",
            business_line_codes=["general"],
            content_hash="hash-1",
            primary_node_id=str(child.node_id),
        )
    )
    db_session.commit()

    tree = get_document_tree(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
    )
    assert len(tree) == 1
    assert tree[0]["node_id"] == str(parent.node_id)
    assert tree[0]["ingested"] is False
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["node_id"] == str(child.node_id)
    assert tree[0]["children"][0]["ingested"] is True


def test_get_document_tree_orders_siblings_by_sort_order(db_session, seeded_kb):
    file_import = _seed_file_import(db_session, seeded_kb.kb_id)
    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.actual_bid,
        source_usage=DocumentSourceUsage.knowledge_extract,
        document_name="sort-order.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()

    root_id = uuid4()
    child_early_id = uuid4()
    child_late_id = uuid4()
    db_session.add_all(
        [
            DocumentTreeNode(
                node_id=root_id,
                kb_id=seeded_kb.kb_id,
                document_id=document.document_id,
                parent_id=None,
                node_type=DocumentTreeNodeType.heading,
                title="一、总则",
                level=1,
                sort_order=0,
                tree_version=1,
            ),
            DocumentTreeNode(
                node_id=child_late_id,
                kb_id=seeded_kb.kb_id,
                document_id=document.document_id,
                parent_id=root_id,
                node_type=DocumentTreeNodeType.heading,
                title="2.2 服务方案",
                level=2,
                sort_order=10,
                tree_version=1,
            ),
            DocumentTreeNode(
                node_id=child_early_id,
                kb_id=seeded_kb.kb_id,
                document_id=document.document_id,
                parent_id=root_id,
                node_type=DocumentTreeNodeType.heading,
                title="1.1 企业介绍",
                level=2,
                sort_order=1,
                tree_version=1,
            ),
        ]
    )
    db_session.commit()

    tree = get_document_tree(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
    )
    child_titles = [child["title"] for child in tree[0]["children"]]
    assert child_titles == ["1.1 企业介绍", "2.2 服务方案"]


def test_list_entry_documents_includes_template_file(db_session, seeded_kb):
    from src.services.knowledge.entry_content_service import list_entry_documents

    file_import = FileImport(
        kb_id=seeded_kb.kb_id,
        file_name="template.docx",
        file_type=FileType.docx,
        file_size=1024,
        storage_path="/tmp/template.docx",
        file_purpose=FilePurpose.template_file,
        status=FileImportStatus.completed,
        hash_status=HashStatus.unavailable,
        created_by="tester",
    )
    db_session.add(file_import)
    db_session.flush()
    document = Document(
        kb_id=seeded_kb.kb_id,
        import_id=file_import.import_id,
        source_type=DocumentSourceType.template_file,
        source_usage=DocumentSourceUsage.knowledge_extract,
        document_name="template.docx",
        parse_status=DocumentParseStatus.ready,
        tree_version=1,
        created_by="tester",
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentTreeNode(
            node_id=uuid4(),
            kb_id=seeded_kb.kb_id,
            document_id=document.document_id,
            parent_id=None,
            node_type=DocumentTreeNodeType.heading,
            title="模板章节",
            level=1,
            sort_order=1,
            tree_version=1,
        )
    )
    db_session.commit()

    rows = list_entry_documents(db_session, seeded_kb.kb_id)
    assert any(row.document_id == document.document_id for row in rows)


def test_get_document_tree_adds_preface_node_when_content_starts_before_first_heading(
    db_session, seeded_kb, tmp_path
):
    document, _, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    source = tmp_path / "content.md"
    source.write_text(
        "封面标题\n\n投标单位：测试公司\n\n# 第一章 总则\n\n正文。\n",
        encoding="utf-8",
    )
    persist_content_md(document_id=document.document_id, source_path=Path(source))

    tree = get_document_tree(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
    )
    assert len(tree) == 2
    assert tree[0]["node_id"] == PREFACE_NODE_ID
    assert tree[0]["title"] == "前言"
    assert tree[0]["level"] == 0
    assert tree[1]["title"] == "第一章 总则"


def test_get_node_preview_returns_preface_content(db_session, seeded_kb, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    document, parent, _ = _seed_document_tree(db_session, seeded_kb.kb_id)
    source = tmp_path / "content.md"
    content_md = "封面标题\n\n投标单位：测试公司\n\n# 第一章 总则\n\n正文。\n"
    source.write_text(content_md, encoding="utf-8")
    persist_content_md(document_id=document.document_id, source_path=Path(source))
    _seed_outline_for_document(
        document_id=document.document_id,
        parent=parent,
        content_md=content_md,
        storage_root=tmp_path,
        monkeypatch=monkeypatch,
    )

    preview = get_node_preview(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=PREFACE_NODE_ID,
    )

    assert preview["title"] == "前言"
    assert "封面标题" in preview["content_md"]
    assert "投标单位" in preview["content_md"]
    assert "# 第一章 总则" not in preview["content_md"]
    assert preview["catalog_path"] == [
        {"node_id": PREFACE_NODE_ID, "title": "前言", "level": 0}
    ]


def test_get_node_preview_uses_anchor_not_db_level(db_session, seeded_kb, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    document, parent, child = _seed_document_tree(db_session, seeded_kb.kb_id)
    content_md = "# 第一章 总则\n\n父节点内容。\n\n## 1.1 范围\n\n子节点内容。\n"
    source = tmp_path / "content.md"
    source.write_text(content_md, encoding="utf-8")
    persist_content_md(document_id=document.document_id, source_path=Path(source))
    _seed_outline_for_document(
        document_id=document.document_id,
        parent=parent,
        child=child,
        content_md=content_md,
        storage_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    parent.level = 3
    db_session.commit()

    preview = get_node_preview(
        db_session,
        kb_id=seeded_kb.kb_id,
        doc_id=document.document_id,
        node_id=parent.node_id,
    )
    assert "子节点内容" in preview["content_md"]
