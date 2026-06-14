#!/usr/bin/env python3
"""Backfill chapter taxonomy on 鼎信 document tree headings and generate pending candidates."""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.db.session import SessionLocal  # noqa: E402
from src.models.actual_bid_parse_task import ActualBidParseTask  # noqa: E402
from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeStatus  # noqa: E402
from src.models.chapter_taxonomy import ChapterTaxonomy  # noqa: E402
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType  # noqa: E402
from src.models.product_category import CategoryStatus, ProductCategory  # noqa: E402
from src.services import candidate_generate_service  # noqa: E402

KB_ID = uuid.UUID("8a27ac63-50c5-401f-998e-200649a94ca5")
IMPORT_ID = uuid.UUID("54e467b9-c3e0-454b-91f8-c47299eae610")
TECH_TAXONOMY_CODE = "technical_solution"
WIKI_TAXONOMY_CODE = "general_requirements"

CHAPTER_TITLE = re.compile(r"^[一二三四五六七八九十]+、")
SUBSECTION_TITLE = re.compile(r"^\d+(\.\d+)*[\.\、]?\s*\S")


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


def _ensure_taxonomy(db, *, kb_id: uuid.UUID, code: str, standard_name: str) -> ChapterTaxonomy:
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


def main() -> int:
    with SessionLocal() as db:
        task = (
            db.query(ActualBidParseTask)
            .filter(ActualBidParseTask.import_id == IMPORT_ID)
            .order_by(ActualBidParseTask.created_at.desc())
            .first()
        )
        if task is None or task.document_id is None:
            print("ERROR: no parse task / document for import", IMPORT_ID)
            return 1

        ku_taxonomy = _ensure_taxonomy(
            db, kb_id=KB_ID, code=TECH_TAXONOMY_CODE, standard_name="技术方案"
        )
        wiki_taxonomy = _ensure_taxonomy(
            db, kb_id=KB_ID, code=WIKI_TAXONOMY_CODE, standard_name="通用要求"
        )

        category = (
            db.query(ProductCategory)
            .filter(ProductCategory.kb_id == KB_ID, ProductCategory.status == CategoryStatus.active)
            .first()
        )
        if category is None:
            category = ProductCategory(
                category_id=uuid.uuid4(),
                kb_id=KB_ID,
                parent_id=None,
                category_name="餐补",
                category_code="meal_subsidy",
                status=CategoryStatus.active,
                path="",
                depth=0,
            )
            category.path = f"/{category.category_id}/"
            db.add(category)
            db.flush()

        headings = (
            db.query(DocumentTreeNode)
            .filter(
                DocumentTreeNode.kb_id == KB_ID,
                DocumentTreeNode.document_id == task.document_id,
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

        created = candidate_generate_service.generate_for_document(
            db,
            kb_id=KB_ID,
            import_id=IMPORT_ID,
            document_id=task.document_id,
            parse_task_id=task.parse_task_id,
        )
        pending_count = (
            db.query(CandidateKnowledge)
            .filter(
                CandidateKnowledge.kb_id == KB_ID,
                CandidateKnowledge.import_id == IMPORT_ID,
                CandidateKnowledge.status == CandidateKnowledgeStatus.pending,
            )
            .count()
        )
        db.commit()

        print(f"document_id={task.document_id}")
        print(f"mapped_headings={mapped}")
        print(f"created_candidates={len(created)}")
        print(f"pending_candidates={pending_count}")
        print(f"ku_taxonomy_id={ku_taxonomy.taxonomy_id}")
        print(f"category_id={category.category_id}")
        return 0 if pending_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
