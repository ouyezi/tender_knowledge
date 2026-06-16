#!/usr/bin/env python3
"""Materialize candidate blocks into document tree for headings without body children."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from uuid import UUID, uuid4

from src.db.session import SessionLocal
from src.models.candidate_knowledge import CandidateKnowledge
from src.models.document import Document
from src.models.document_tree_node import DocumentTreeNode, DocumentTreeNodeType
from src.services.content_blocks import parse_content
from src.services.doc_chunk.linkage_validation import titles_compatible


def _heading_has_body_children(db, heading_node_id: UUID) -> bool:
    return (
        db.query(DocumentTreeNode.node_id)
        .filter(
            DocumentTreeNode.parent_id == heading_node_id,
            DocumentTreeNode.node_type != DocumentTreeNodeType.heading,
        )
        .first()
        is not None
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb-id", required=True)
    parser.add_argument("--import-id")
    parser.add_argument("--document-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    kb_id = UUID(args.kb_id)
    created = 0
    skipped = 0

    with SessionLocal() as db:
        doc_q = db.query(Document).filter(Document.kb_id == kb_id)
        if args.import_id:
            doc_q = doc_q.filter(Document.import_id == UUID(args.import_id))
        if args.document_id:
            doc_q = doc_q.filter(Document.document_id == UUID(args.document_id))
        documents = doc_q.all()

        for document in documents:
            candidates = (
                db.query(CandidateKnowledge)
                .filter(
                    CandidateKnowledge.kb_id == kb_id,
                    CandidateKnowledge.source_doc_id == document.document_id,
                )
                .all()
            )
            for candidate in candidates:
                if not candidate.source_node_id:
                    skipped += 1
                    continue
                heading = db.get(DocumentTreeNode, candidate.source_node_id)
                if heading is None or heading.node_type != DocumentTreeNodeType.heading:
                    skipped += 1
                    continue
                if _heading_has_body_children(db, heading.node_id):
                    skipped += 1
                    continue
                if not titles_compatible(heading.title, candidate.title):
                    skipped += 1
                    continue
                parsed = parse_content(candidate.content)
                if not parsed.blocks:
                    skipped += 1
                    continue

                for index, block in enumerate(parsed.blocks):
                    block_type = block.get("type")
                    if block_type not in {"paragraph", "table", "image"}:
                        continue
                    node_type = DocumentTreeNodeType.paragraph
                    content_preview = None
                    content_ref = None
                    if block_type in {"paragraph", "table"}:
                        node_type = (
                            DocumentTreeNodeType.paragraph
                            if block_type == "paragraph"
                            else DocumentTreeNodeType.table
                        )
                        text = str(block.get("text") or "").strip()
                        if not text:
                            continue
                        content_preview = text[:4000]
                    else:
                        node_type = DocumentTreeNodeType.image
                        asset_id = block.get("asset_id")
                        content_ref = str(asset_id) if asset_id else None

                    created += 1
                    if args.dry_run:
                        continue
                    db.add(
                        DocumentTreeNode(
                            node_id=uuid4(),
                            kb_id=kb_id,
                            document_id=document.document_id,
                            parent_id=heading.node_id,
                            node_type=node_type,
                            title=None,
                            level=None,
                            sort_order=heading.sort_order * 1000 + index + 1,
                            content_ref=content_ref,
                            content_preview=content_preview,
                            chapter_taxonomy_id=None,
                            product_category_ids=[],
                            is_outline_node=False,
                            candidate_template_chapter_id=None,
                            candidate_pattern_id=None,
                            needs_manual_review=False,
                            tree_version=document.tree_version,
                        )
                    )
        if not args.dry_run:
            db.commit()

    print(json.dumps({"created": created, "skipped": skipped, "dry_run": args.dry_run}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
