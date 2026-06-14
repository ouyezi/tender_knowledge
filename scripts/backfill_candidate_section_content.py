#!/usr/bin/env python3
"""Backfill CandidateKnowledge.content using section_content_builder."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from uuid import UUID

from src.db.session import SessionLocal
from src.models.candidate_knowledge import CandidateKnowledge, CandidateKnowledgeStatus
from src.services.section_content_builder import build_section_content


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb-id", required=True)
    parser.add_argument("--import-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    kb_id = UUID(args.kb_id)
    updated = 0
    with SessionLocal() as db:
        q = db.query(CandidateKnowledge).filter(
            CandidateKnowledge.kb_id == kb_id,
            CandidateKnowledge.status == CandidateKnowledgeStatus.pending,
        )
        if args.import_id:
            q = q.filter(CandidateKnowledge.import_id == UUID(args.import_id))
        for row in q.all():
            if not row.source_doc_id or not row.source_node_id:
                continue
            new_content = build_section_content(
                db,
                document_id=row.source_doc_id,
                heading_node_id=row.source_node_id,
            )
            if new_content == row.content:
                continue
            updated += 1
            if not args.dry_run:
                row.content = new_content
        if not args.dry_run:
            db.commit()
    print(f"updated={updated} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
