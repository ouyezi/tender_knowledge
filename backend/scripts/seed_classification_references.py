"""Seed classification references for local impact-analysis demos."""

from __future__ import annotations

import os
import sys
import uuid

from sqlalchemy import select

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.session import SessionLocal
from src.models.classification_reference import (
    ClassificationReference,
    ClassificationType,
    ReferenceObjectType,
)
from src.models.knowledge_base import KnowledgeBase
from src.models.product_category import ProductCategory


def main() -> None:
    db = SessionLocal()
    try:
        kb = db.scalar(select(KnowledgeBase).limit(1))
        if kb is None:
            print("No knowledge base found; create one first.")
            return

        category = db.scalar(
            select(ProductCategory).where(ProductCategory.kb_id == kb.kb_id).limit(1)
        )
        if category is None:
            print("No product category found; create one first.")
            return

        existing = db.scalar(
            select(ClassificationReference.reference_id).where(
                ClassificationReference.kb_id == kb.kb_id,
                ClassificationReference.classification_id == category.category_id,
            )
        )
        if existing is not None:
            print("References already seeded for first category; skipping.")
            return

        for _ in range(5):
            db.add(
                ClassificationReference(
                    kb_id=kb.kb_id,
                    classification_type=ClassificationType.product_category,
                    classification_id=category.category_id,
                    object_type=ReferenceObjectType.ku,
                    object_id=uuid.uuid4(),
                )
            )
        for _ in range(3):
            db.add(
                ClassificationReference(
                    kb_id=kb.kb_id,
                    classification_type=ClassificationType.product_category,
                    classification_id=category.category_id,
                    object_type=ReferenceObjectType.candidate_knowledge,
                    object_id=uuid.uuid4(),
                )
            )
        db.commit()
        print(
            f"Seeded 8 references for category {category.category_id} in KB {kb.kb_id}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
