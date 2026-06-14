from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from src.models.chapter_taxonomy import ChapterTaxonomy
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.models.product_category import CategoryStatus, ProductCategory

CHAPTER_TITLE = re.compile(r"^[一二三四五六七八九十]+、")
SUBSECTION_TITLE = re.compile(r"^\d+(\.\d+)*[\.\、]?\s*\S")
TECH_TAXONOMY_CODE = "technical_solution"
WIKI_TAXONOMY_CODE = "general_requirements"


def _should_map_heading(title: str, level: int) -> bool:
    text = (title or "").strip()
    if not text or len(text) < 2:
        return False
    if re.search(r"20\d{2}\s*年", text):
        return False
    if CHAPTER_TITLE.match(text):
        return True
    if "服务方案" in text or "技术方案" in text or "业绩" in text:
        return True
    return level <= 2 and SUBSECTION_TITLE.match(text) is not None


def _ensure_taxonomy(db: Session, *, kb_id: uuid.UUID, code: str, standard_name: str) -> ChapterTaxonomy:
    row = (
        db.query(ChapterTaxonomy)
        .filter(ChapterTaxonomy.kb_id == kb_id, ChapterTaxonomy.taxonomy_code == code)
        .first()
    )
    if row is not None:
        return row
    taxonomy = ChapterTaxonomy(
        taxonomy_id=uuid.uuid4(),
        kb_id=kb_id,
        parent_id=None,
        standard_name=standard_name,
        taxonomy_code=code,
        status=CategoryStatus.active,
        path="",
        depth=0,
    )
    taxonomy.path = f"/{taxonomy.taxonomy_id}/"
    db.add(taxonomy)
    db.flush()
    return taxonomy


def _ensure_category(db: Session, *, kb_id: uuid.UUID) -> ProductCategory:
    category = (
        db.query(ProductCategory)
        .filter(ProductCategory.kb_id == kb_id, ProductCategory.status == CategoryStatus.active)
        .first()
    )
    if category is not None:
        return category
    category = ProductCategory(
        category_id=uuid.uuid4(),
        kb_id=kb_id,
        parent_id=None,
        category_name="E2E默认分类",
        category_code="e2e_default",
        status=CategoryStatus.active,
        path="",
        depth=0,
    )
    category.path = f"/{category.category_id}/"
    db.add(category)
    db.flush()
    return category


def backfill_taxonomy_for_document(db: Session, *, kb_id: uuid.UUID, document_id: uuid.UUID) -> int:
    ku_taxonomy = _ensure_taxonomy(
        db, kb_id=kb_id, code=TECH_TAXONOMY_CODE, standard_name="技术方案"
    )
    wiki_taxonomy = _ensure_taxonomy(
        db, kb_id=kb_id, code=WIKI_TAXONOMY_CODE, standard_name="通用要求"
    )
    category = _ensure_category(db, kb_id=kb_id)

    headings = (
        db.query(DocumentTreeNode)
        .filter(
            DocumentTreeNode.kb_id == kb_id,
            DocumentTreeNode.document_id == document_id,
            DocumentTreeNode.node_type == DocumentTreeNodeType.heading,
        )
        .order_by(DocumentTreeNode.sort_order.asc())
        .all()
    )

    mapped = 0
    for node in headings:
        if not _should_map_heading(node.title or "", node.level):
            continue
        title = (node.title or "").strip()
        if "响应函" in title or "报价表" in title or "授权书" in title or "身份证明" in title:
            node.chapter_taxonomy_id = wiki_taxonomy.taxonomy_id
        else:
            node.chapter_taxonomy_id = ku_taxonomy.taxonomy_id
        if not node.product_category_ids:
            node.product_category_ids = [str(category.category_id)]
        mapped += 1
    db.flush()
    return mapped
