from src.db.session import Base
from src.models.chunk_asset import ChunkAsset
from src.models.chunk_embedding import ChunkEmbedding
from src.models.knowledge_chunk import KnowledgeChunk


def test_knowledge_v2_tables_registered():
    tables = set(Base.metadata.tables.keys())
    assert "knowledge_chunks" in tables
    assert "chunk_assets" in tables
    assert "chunk_embeddings" in tables


def test_knowledge_chunk_has_kb_id_and_partial_unique_index():
    indexes = {idx.name: idx for idx in KnowledgeChunk.__table__.indexes}
    assert "uq_knowledge_chunks_latest_node" in indexes
    cols = {c.name for c in KnowledgeChunk.__table__.columns}
    assert "kb_id" in cols
    assert "primary_node_id" in cols
