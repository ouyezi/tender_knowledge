from uuid import uuid4

import pytest

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.blueprint_embedding import BlueprintEmbedding
from src.models.knowledge_blueprint import BlueprintStatus, KnowledgeBlueprint
from src.services.knowledge.blueprint_search_service import (
    BlueprintSearchValidationError,
    search_blueprints,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed(db_session, kb_id, *, name: str, tags: list[str], embedding: list[float] | None):
    blueprint_id = uuid4()
    bp = KnowledgeBlueprint(
        blueprint_id=blueprint_id,
        kb_id=kb_id,
        name=name,
        description="desc",
        source_doc_id=uuid4(),
        source_node_id=uuid4(),
        product_tags=tags,
        industry_tags=[],
        scenario_tags=[],
        applicable_project_type=[],
        status=BlueprintStatus.active,
    )
    db_session.add(bp)
    emb = BlueprintEmbedding(
        blueprint_id=blueprint_id,
        kb_id=kb_id,
        search_text=name,
        embedding=embedding,
        embedding_status="ready" if embedding else "pending",
        content_hash="x",
    )
    db_session.add(emb)
    db_session.commit()
    return blueprint_id


def test_search_blueprints_keyword_only(db_session, seeded_kb):
    _seed(db_session, seeded_kb.kb_id, name="政务云架构", tags=["政务云"], embedding=None)
    result = search_blueprints(
        db_session,
        kb_id=seeded_kb.kb_id,
        semantic_query="",
        keyword="政务云",
        product_tags=[],
        industry_tags=[],
        scenario_tags=[],
        vector_weight=0.6,
        keyword_weight=0.4,
        top_k=10,
        query_vector=None,
    )
    assert result["total"] == 1
    assert result["items"][0]["name"] == "政务云架构"


def test_search_blueprints_empty_query_raises():
    with pytest.raises(BlueprintSearchValidationError):
        search_blueprints(
            None,  # type: ignore[arg-type]
            kb_id=uuid4(),
            semantic_query="",
            keyword="",
            product_tags=[],
            industry_tags=[],
            scenario_tags=[],
            vector_weight=0.6,
            keyword_weight=0.4,
            top_k=10,
            query_vector=None,
        )


def test_search_exact_title_beats_noisy_vector(db_session, seeded_kb):
    query_vector = [1.0, 0.0, 0.0, 0.0]
    noisy_embedding = [0.079, 0.99687, 0.0, 0.0]
    target_embedding = [0.018, 0.99984, 0.0, 0.0]
    _seed(
        db_session,
        seeded_kb.kb_id,
        name="企业资质",
        tags=[],
        embedding=noisy_embedding,
    )
    _seed(
        db_session,
        seeded_kb.kb_id,
        name="餐补产品功能介绍",
        tags=[],
        embedding=target_embedding,
    )
    result = search_blueprints(
        db_session,
        kb_id=seeded_kb.kb_id,
        semantic_query="餐补产品功能介绍",
        keyword="餐补 产品 功能 介绍",
        product_tags=[],
        industry_tags=[],
        scenario_tags=[],
        vector_weight=0.6,
        keyword_weight=0.4,
        top_k=10,
        query_vector=query_vector,
    )
    assert result["items"][0]["name"] == "餐补产品功能介绍"
    assert result["items"][0]["score_detail"]["exact_match_bonus"] == 0.35
