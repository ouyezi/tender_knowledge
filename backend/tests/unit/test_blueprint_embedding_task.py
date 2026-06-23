from uuid import uuid4

from src.models.blueprint_embedding import BlueprintEmbedding
from src.models.knowledge_blueprint import KnowledgeBlueprint
from src.services.knowledge.blueprint_embedding_task import embed_blueprint
from src.services.knowledge.embedding_client import EmbeddingResult


def _seed_blueprint(db_session, kb_id):
    blueprint_id = uuid4()
    doc_id = uuid4()
    node_id = uuid4()
    row = KnowledgeBlueprint(
        blueprint_id=blueprint_id,
        kb_id=kb_id,
        name="政务云蓝图",
        description="技术架构章节",
        source_doc_id=doc_id,
        source_node_id=node_id,
        product_tags=["政务云"],
        industry_tags=[],
        scenario_tags=[],
        applicable_project_type=[],
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_embed_blueprint_creates_ready_row(db_session, seeded_kb, monkeypatch):
    blueprint = _seed_blueprint(db_session, seeded_kb.kb_id)

    def fake_embed(_self, text: str) -> EmbeddingResult:
        return EmbeddingResult(vector=[0.1] * 8)

    monkeypatch.setattr(
        "src.services.knowledge.blueprint_embedding_task.EmbeddingClient.embed_text",
        fake_embed,
    )
    monkeypatch.setenv("EMBEDDING_API_BASE", "https://embedding.test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")

    status = embed_blueprint(db_session, blueprint.blueprint_id)

    assert status == "ready"
    row = db_session.get(BlueprintEmbedding, blueprint.blueprint_id)
    assert row is not None
    assert row.embedding_status == "ready"
    assert "政务云蓝图" in row.search_text


def _clear_embedding_credentials(monkeypatch):
    monkeypatch.delenv("EMBEDDING_API_BASE", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.setattr("src.config.settings.embedding_api_base", None)
    monkeypatch.setattr("src.config.settings.embedding_api_key", None)
    monkeypatch.setattr("src.config.settings.llm_api_key", None)


def test_embed_blueprint_skipped_when_not_configured(db_session, seeded_kb, monkeypatch):
    blueprint = _seed_blueprint(db_session, seeded_kb.kb_id)
    _clear_embedding_credentials(monkeypatch)

    status = embed_blueprint(db_session, blueprint.blueprint_id)

    assert status == "skipped"
