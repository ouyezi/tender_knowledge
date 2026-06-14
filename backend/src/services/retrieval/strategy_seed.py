from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.models.retrieval_strategy_version import RetrievalStrategyVersion


DEFAULT_STRATEGY_CONFIG = {
    "intents": {
        "knowledge_lookup": {
            "enable_bm25": True,
            "enable_vector": True,
            "enable_rerank": False,
            "top_k": 20,
        },
        "material_recommend": {
            "enable_bm25": True,
            "enable_vector": True,
            "enable_rerank": True,
            "top_k": 15,
        },
        "module_suggestion": {"enable_structure": True, "top_k": 10},
        "trace_lookup": {"top_k": 1},
        "directory_match": {"enable_structure": True, "top_k": 10},
    },
    "bm25_weights": {"title": 0.6, "content": 0.4},
    "match_score_weights": {
        "product_category": 0.3,
        "chapter_taxonomy": 0.3,
        "title_similarity": 0.2,
        "level_order": 0.1,
        "knowledge_coverage": 0.1,
    },
    "gap_threshold": {"min_frequency": 3, "min_ratio": 0.3},
    "context_expand_depth": 1,
}


def seed_default_strategy(db: Session, kb_id: UUID, created_by: str = "system") -> RetrievalStrategyVersion:
    existing = (
        db.query(RetrievalStrategyVersion)
        .filter(RetrievalStrategyVersion.kb_id == kb_id)
        .filter(RetrievalStrategyVersion.name == "default")
        .filter(RetrievalStrategyVersion.version_tag == "1.0.0")
        .one_or_none()
    )
    if existing is not None:
        return existing

    (
        db.query(RetrievalStrategyVersion)
        .filter(RetrievalStrategyVersion.kb_id == kb_id)
        .update({"is_active": False}, synchronize_session=False)
    )
    strategy = RetrievalStrategyVersion(
        kb_id=kb_id,
        name="default",
        version_tag="1.0.0",
        config=DEFAULT_STRATEGY_CONFIG,
        is_active=True,
        created_by=created_by,
        notes="Seeded default strategy for Epic 5.",
    )
    db.add(strategy)
    db.flush()
    return strategy
