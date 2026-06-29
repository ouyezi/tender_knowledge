from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.knowledge_taxonomy import KnowledgeTaxonomy
from src.services.knowledge.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS


def seed_knowledge_taxonomy(db: Session) -> None:
    if db.query(KnowledgeTaxonomy).count() > 0:
        return
    for row in KNOWLEDGE_TAXONOMY_SEED_ROWS:
        db.add(
            KnowledgeTaxonomy(
                kb_id=None,
                dimension=row["dimension"],
                code=row["code"],
                parent_code=row["parent_code"],
                label=row["label"],
                label_en=row["label_en"],
                level=row["level"],
                sort_order=row["sort_order"],
                is_active=row["is_active"],
                metadata_json=row["metadata"],
            )
        )
    db.commit()
