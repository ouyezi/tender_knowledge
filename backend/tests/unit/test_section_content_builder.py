# backend/tests/unit/test_section_content_builder.py
from uuid import uuid4

from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.section_content_builder import build_section_content, build_section_direct_content


def _node(
    *,
    document_id,
    sort_order: int,
    node_type: DocumentTreeNodeType,
    title: str | None = None,
    level: int | None = None,
    content_preview: str | None = None,
    content_ref: str | None = None,
):
    return DocumentTreeNode(
        node_id=uuid4(),
        kb_id=uuid4(),
        document_id=document_id,
        parent_id=None,
        node_type=node_type,
        title=title,
        level=level,
        sort_order=sort_order,
        content_preview=content_preview,
        content_ref=content_ref,
        tree_version=1,
    )


def test_build_section_content_collects_until_sibling_heading(db_session):
    document_id = uuid4()
    h1 = _node(
        document_id=document_id,
        sort_order=0,
        node_type=DocumentTreeNodeType.heading,
        title="技术方案",
        level=1,
        content_preview="技术方案",
    )
    p1 = _node(
        document_id=document_id,
        sort_order=1,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落一",
    )
    h2 = _node(
        document_id=document_id,
        sort_order=2,
        node_type=DocumentTreeNodeType.heading,
        title="子方案",
        level=2,
        content_preview="子方案",
    )
    p2 = _node(
        document_id=document_id,
        sort_order=3,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落二",
    )
    p3 = _node(
        document_id=document_id,
        sort_order=4,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落三",
    )
    db_session.add_all([h1, p1, h2, p2, p3])
    db_session.commit()

    content = build_section_content(
        db_session,
        document_id=document_id,
        heading_node_id=h1.node_id,
    )
    from src.services.content_blocks import parse_content

    doc = parse_content(content)
    texts = [b.get("text") for b in doc.blocks if b.get("type") == "paragraph"]
    assert texts == ["段落一", "段落三"]


def test_build_section_content_nested_heading_candidate(db_session):
    document_id = uuid4()
    h2 = _node(
        document_id=document_id,
        sort_order=2,
        node_type=DocumentTreeNodeType.heading,
        title="子方案",
        level=2,
        content_preview="子方案",
    )
    p2 = _node(
        document_id=document_id,
        sort_order=3,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落二",
    )
    db_session.add_all([h2, p2])
    db_session.commit()

    content = build_section_content(
        db_session,
        document_id=document_id,
        heading_node_id=h2.node_id,
    )
    from src.services.content_blocks import parse_content

    doc = parse_content(content)
    assert len(doc.blocks) == 1
    assert doc.blocks[0]["text"] == "段落二"


def test_build_section_direct_content_excludes_nested_subheading_bodies(db_session):
    document_id = uuid4()
    h1 = _node(
        document_id=document_id,
        sort_order=0,
        node_type=DocumentTreeNodeType.heading,
        title="技术方案",
        level=1,
        content_preview="技术方案",
    )
    p1 = _node(
        document_id=document_id,
        sort_order=1,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落一",
    )
    h2 = _node(
        document_id=document_id,
        sort_order=2,
        node_type=DocumentTreeNodeType.heading,
        title="子方案",
        level=2,
        content_preview="子方案",
    )
    p2 = _node(
        document_id=document_id,
        sort_order=3,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="段落二",
    )
    db_session.add_all([h1, p1, h2, p2])
    db_session.commit()

    content = build_section_direct_content(
        db_session,
        document_id=document_id,
        heading_node_id=h1.node_id,
    )
    from src.services.content_blocks import parse_content

    doc = parse_content(content)
    texts = [b.get("text") for b in doc.blocks if b.get("type") == "paragraph"]
    assert texts == ["段落一"]


def test_build_section_content_uses_parent_id_tree_when_sort_order_splits(db_session):
    """Large docs materialize headings before body; parent_id holds the real section tree."""
    document_id = uuid4()
    h1 = _node(
        document_id=document_id,
        sort_order=0,
        node_type=DocumentTreeNodeType.heading,
        title="十、应急处理",
        level=8,
        content_preview="十、应急处理",
    )
    p1 = _node(
        document_id=document_id,
        sort_order=500,
        node_type=DocumentTreeNodeType.paragraph,
        content_preview="应急正文段落",
    )
    p1.parent_id = h1.node_id
    db_session.add_all([h1, p1])
    db_session.commit()

    content = build_section_content(
        db_session,
        document_id=document_id,
        heading_node_id=h1.node_id,
    )
    from src.services.content_blocks import parse_content

    doc = parse_content(content)
    assert [b.get("text") for b in doc.blocks if b.get("type") == "paragraph"] == ["应急正文段落"]
