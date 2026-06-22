# Blueprint Semantic Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付目录蓝图语义检索全栈能力：蓝图级异步向量索引、可配置权重的关键词+向量混合搜索 API、LLM 自然语言解析，以及列表页语义搜索入口。

**Architecture:** 新建 `blueprint_embeddings` 表与 `blueprint_embedding_task`（复用 `EmbeddingClient`）；`blueprint_search_service` 在 SQL 硬过滤后对候选蓝图做 Python 侧打分与高亮；`blueprint_query_parse_service` 无状态 LLM 拆分查询参数；`create`/`update` 通过 `BackgroundTasks` 触发索引。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pgvector, pytest; React 18, TypeScript, Ant Design 5.

**Design spec:** `docs/superpowers/specs/2026-06-22-blueprint-semantic-search-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/config.py` | `blueprint_search_parse_*` 配置 |
| `.env.example` | 文档化新环境变量 |
| `backend/alembic/versions/20260622_1200_blueprint_embeddings.py` | DDL |
| `backend/src/models/blueprint_embedding.py` | ORM |
| `backend/src/models/__init__.py` | 导出新模型 |
| `backend/tests/conftest.py` | 注册 blueprint 模型 import |
| `backend/src/services/knowledge/blueprint_index_text.py` | `search_text` 拼接、hash、关键词分、高亮 |
| `backend/src/services/knowledge/blueprint_embedding_task.py` | 索引构建/重建 |
| `backend/src/services/knowledge/blueprint_search_service.py` | 混合检索 |
| `backend/src/services/knowledge/blueprint_query_parse_service.py` | LLM 解析 |
| `backend/src/api/schemas/blueprints.py` | 新 Pydantic schema |
| `backend/src/api/routes/blueprints.py` | 新端点 + BackgroundTasks |
| `backend/tests/unit/test_blueprint_index_text.py` | 文本工具单元测试 |
| `backend/tests/unit/test_blueprint_embedding_task.py` | 索引任务单元测试 |
| `backend/tests/unit/test_blueprint_search_service.py` | 检索服务单元测试 |
| `backend/tests/unit/test_blueprint_query_parse_service.py` | LLM 解析单元测试 |
| `backend/tests/integration/test_blueprint_search_api.py` | API 集成测试 |
| `frontend/src/services/blueprints.ts` | API client + 类型 |
| `frontend/src/pages/Knowledge/BlueprintListPage.tsx` | 语义搜索 UI |

---

## Task 1: 配置项

**Files:**
- Modify: `backend/src/config.py`
- Modify: `.env.example`
- Modify: `backend/tests/unit/test_blueprint_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_blueprint_config.py — append:

def test_blueprint_search_parse_defaults():
    assert settings.blueprint_search_parse_model == "qwen3.6-flash"
    assert settings.blueprint_search_parse_timeout_sec == 30
    assert settings.blueprint_search_parse_query_max == 500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_config.py::test_blueprint_search_parse_defaults -v`

Expected: FAIL with `AttributeError: blueprint_search_parse_model`

- [ ] **Step 3: Add settings**

```python
# backend/src/config.py — after blueprint_suggest_requirement_max:
    blueprint_search_parse_model: str = "qwen3.6-flash"
    blueprint_search_parse_timeout_sec: int = 30
    blueprint_search_parse_query_max: int = 500
```

```bash
# .env.example — append:
BLUEPRINT_SEARCH_PARSE_MODEL=qwen3.6-flash
BLUEPRINT_SEARCH_PARSE_TIMEOUT_SEC=30
BLUEPRINT_SEARCH_PARSE_QUERY_MAX=500
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/config.py .env.example backend/tests/unit/test_blueprint_config.py
git commit -m "feat: add blueprint semantic search parse config"
```

---

## Task 2: 数据模型与 Migration

**Files:**
- Create: `backend/src/models/blueprint_embedding.py`
- Create: `backend/alembic/versions/20260622_1200_blueprint_embeddings.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Create ORM model**

```python
# backend/src/models/blueprint_embedding.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class BlueprintEmbedding(Base):
    __tablename__ = "blueprint_embeddings"

    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_blueprints.blueprint_id", ondelete="CASCADE"),
        primary_key=True,
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[Any] = mapped_column(
        JSON().with_variant(Vector(1024), "postgresql"), nullable=True
    )
    embedding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Register model**

```python
# backend/src/models/__init__.py — add:
from src.models.blueprint_embedding import BlueprintEmbedding

# __all__ append "BlueprintEmbedding"
```

```python
# backend/tests/conftest.py — in models import block add:
    knowledge_blueprint,
    knowledge_blueprint_node,
    blueprint_embedding,
```

- [ ] **Step 3: Create migration**

```python
# backend/alembic/versions/20260622_1200_blueprint_embeddings.py
"""blueprint embeddings for semantic search

Revision ID: 20260622_1200
Revises: 20260622_1100
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260622_1200"
down_revision: str | None = "20260622_1100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    op.create_table(
        "blueprint_embeddings",
        sa.Column("blueprint_id", sa.Uuid(), nullable=False),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("embedding_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["blueprint_id"], ["knowledge_blueprints.blueprint_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("blueprint_id"),
    )
    op.create_index("ix_blueprint_embeddings_kb_id", "blueprint_embeddings", ["kb_id"])


def downgrade() -> None:
    op.drop_index("ix_blueprint_embeddings_kb_id", table_name="blueprint_embeddings")
    op.drop_table("blueprint_embeddings")
```

- [ ] **Step 4: Verify models load**

Run: `cd backend && ../.venv/bin/python -c "from src.models.blueprint_embedding import BlueprintEmbedding; print(BlueprintEmbedding.__tablename__)"`

Expected: `blueprint_embeddings`

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/blueprint_embedding.py backend/src/models/__init__.py \
  backend/alembic/versions/20260622_1200_blueprint_embeddings.py backend/tests/conftest.py
git commit -m "feat: add blueprint_embeddings table and ORM model"
```

---

## Task 3: 索引文本工具（search_text / hash / 关键词分 / 高亮）

**Files:**
- Create: `backend/src/services/knowledge/blueprint_index_text.py`
- Create: `backend/tests/unit/test_blueprint_index_text.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_blueprint_index_text.py
from src.services.knowledge.blueprint_index_text import (
    build_search_text,
    compute_content_hash,
    keyword_score,
    build_highlights,
)


SAMPLE_DETAIL = {
    "name": "政务云技术方案",
    "description": "面向政府的云架构蓝图",
    "product_tags": ["政务云"],
    "industry_tags": ["政府"],
    "scenario_tags": ["IaaS"],
    "applicable_project_type": ["信息化建设"],
    "suggested_structure_md": "## 技术架构",
    "nodes": [
        {
            "node_title": "总体架构",
            "content_description": "描述云平台分层",
            "tender_response_hint": "响应架构评分点",
            "children": [],
        }
    ],
}


def test_build_search_text_includes_name_and_nodes():
    text = build_search_text(SAMPLE_DETAIL)
    assert "政务云技术方案" in text
    assert "总体架构" in text
    assert "政务云" in text


def test_compute_content_hash_stable():
    h1 = compute_content_hash("abc")
    h2 = compute_content_hash("abc")
    assert h1 == h2
    assert h1 != compute_content_hash("xyz")


def test_keyword_score_matches_name():
    score = keyword_score(
        keyword="政务云",
        name="政务云技术方案",
        description="",
        search_text="政务云技术方案",
    )
    assert score == 1.0


def test_build_highlights_wraps_em():
    highlights = build_highlights(
        keyword="政务云 技术",
        name="政务云技术方案",
        description="",
        search_text="政务云技术方案描述",
    )
    assert highlights
    assert "<em>" in highlights[0]["snippet"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_index_text.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# backend/src/services/knowledge/blueprint_index_text.py
from __future__ import annotations

import hashlib
import re
from typing import Any


def _join_tags(tags: list[Any] | None) -> str:
    return " ".join(str(item).strip() for item in (tags or []) if str(item).strip())


def _flatten_nodes(nodes: list[dict[str, Any]]) -> list[str]:
    parts: list[str] = []
    for node in nodes or []:
        title = str(node.get("node_title") or "").strip()
        cd = str(node.get("content_description") or "").strip()
        tr = str(node.get("tender_response_hint") or "").strip()
        if title:
            parts.append(title)
        if cd:
            parts.append(cd)
        if tr:
            parts.append(tr)
        parts.extend(_flatten_nodes(node.get("children") or []))
    return parts


def build_search_text(detail: dict[str, Any]) -> str:
    sections = [
        str(detail.get("name") or "").strip(),
        str(detail.get("description") or "").strip(),
        _join_tags(detail.get("product_tags")),
        _join_tags(detail.get("industry_tags")),
        _join_tags(detail.get("scenario_tags")),
        _join_tags(detail.get("applicable_project_type")),
        str(detail.get("suggested_structure_md") or "").strip(),
        *_flatten_nodes(detail.get("nodes") or []),
    ]
    return "\n".join(part for part in sections if part)


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _keyword_tokens(keyword: str) -> list[str]:
    return [token for token in re.split(r"\s+", keyword.strip()) if token]


def keyword_score(*, keyword: str, name: str, description: str | None, search_text: str) -> float:
    tokens = _keyword_tokens(keyword)
    if not tokens:
        return 0.0
    fields = [name or "", description or "", search_text or ""]
    matched = 0
    for token in tokens:
        token_lower = token.lower()
        if any(token_lower in field.lower() for field in fields):
            matched += 1
    return matched / len(tokens)


def _highlight_text(text: str, keyword: str, *, field: str, max_len: int = 200) -> dict[str, str] | None:
    tokens = _keyword_tokens(keyword)
    if not text or not tokens:
        return None
    snippet = text[:max_len]
    for token in tokens:
        pattern = re.compile(re.escape(token), re.IGNORECASE)
        snippet = pattern.sub(lambda m: f"<em>{m.group(0)}</em>", snippet)
    if "<em>" not in snippet:
        return None
    return {"field": field, "snippet": snippet}


def build_highlights(
    *,
    keyword: str,
    name: str,
    description: str | None,
    search_text: str,
) -> list[dict[str, str]]:
    highlights: list[dict[str, str]] = []
    for field, value in (
        ("name", name),
        ("description", description or ""),
        ("search_text", search_text),
    ):
        item = _highlight_text(value, keyword, field=field)
        if item:
            highlights.append(item)
    return highlights
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_index_text.py -v`

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_index_text.py backend/tests/unit/test_blueprint_index_text.py
git commit -m "feat: add blueprint index text utilities"
```

---

## Task 4: 索引构建任务（embed_blueprint / rebuild）

**Files:**
- Create: `backend/src/services/knowledge/blueprint_embedding_task.py`
- Create: `backend/tests/unit/test_blueprint_embedding_task.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_blueprint_embedding_task.py
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


def test_embed_blueprint_skipped_when_not_configured(db_session, seeded_kb, monkeypatch):
    blueprint = _seed_blueprint(db_session, seeded_kb.kb_id)
    monkeypatch.delenv("EMBEDDING_API_BASE", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)

    status = embed_blueprint(db_session, blueprint.blueprint_id)

    assert status == "skipped"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_embedding_task.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# backend/src/services/knowledge/blueprint_embedding_task.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import settings
from src.models.blueprint_embedding import BlueprintEmbedding
from src.models.knowledge_blueprint import KnowledgeBlueprint
from src.services.knowledge.blueprint_index_text import build_search_text, compute_content_hash
from src.services.knowledge.blueprint_service import BlueprintNotFoundError, get_blueprint_detail
from src.services.knowledge.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)


def _embedding_client() -> EmbeddingClient:
    return EmbeddingClient(model=settings.embedding_model)


def embed_blueprint(db: Session, blueprint_id: UUID) -> str:
    blueprint = db.get(KnowledgeBlueprint, blueprint_id)
    if blueprint is None:
        return "failed"

    detail = get_blueprint_detail(db, kb_id=blueprint.kb_id, blueprint_id=blueprint_id)
    search_text = build_search_text(detail)
    content_hash = compute_content_hash(search_text)

    row = db.get(BlueprintEmbedding, blueprint_id)
    if row is None:
        row = BlueprintEmbedding(
            blueprint_id=blueprint_id,
            kb_id=blueprint.kb_id,
            search_text=search_text,
            embedding_status="pending",
        )
        db.add(row)
    elif row.content_hash == content_hash and row.embedding_status == "ready":
        return "ready"
    else:
        row.search_text = search_text
        row.content_hash = content_hash
        row.embedding_status = "pending"

    client = _embedding_client()
    if not client.is_configured:
        row.embedding_status = "skipped"
        row.indexed_at = datetime.now(timezone.utc)
        db.commit()
        return "skipped"

    result = client.embed_text(search_text)
    if result.vector is None:
        row.embedding_status = "failed"
        row.embedding = None
        row.indexed_at = datetime.now(timezone.utc)
        db.commit()
        return "failed"

    row.embedding = result.vector
    row.embedding_status = "ready"
    row.indexed_at = datetime.now(timezone.utc)
    db.commit()
    return "ready"


def rebuild_blueprints_for_kb(db: Session, *, kb_id: UUID) -> int:
    rows = (
        db.query(KnowledgeBlueprint.blueprint_id)
        .filter(KnowledgeBlueprint.kb_id == kb_id, KnowledgeBlueprint.status == "active")
        .all()
    )
    count = 0
    for (blueprint_id,) in rows:
        embed_blueprint(db, blueprint_id)
        count += 1
    return count


def get_blueprint_embedding_status(db: Session, blueprint_id: UUID) -> str:
    row = db.get(BlueprintEmbedding, blueprint_id)
    if row is None:
        return "pending"
    return row.embedding_status
```

Add helper `_embed_blueprint_in_background` in routes (Task 8) mirroring `knowledge_chunks.py`.

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_embedding_task.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_embedding_task.py backend/tests/unit/test_blueprint_embedding_task.py
git commit -m "feat: add blueprint embedding index task"
```

---

## Task 5: 混合检索服务

**Files:**
- Create: `backend/src/services/knowledge/blueprint_search_service.py`
- Create: `backend/tests/unit/test_blueprint_search_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_blueprint_search_service.py
from uuid import uuid4

from src.models.blueprint_embedding import BlueprintEmbedding
from src.models.knowledge_blueprint import KnowledgeBlueprint
from src.services.knowledge.blueprint_search_service import search_blueprints


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


def test_search_blueprints_keyword_only(db_session, seeded_kb, monkeypatch):
    _seed(db_session, seeded_kb.kb_id, name="政务云架构", tags=["政务云"], embedding=None)
    result = search_blueprints(
        db_session,
        kb_id=seeded_kb.kb_id,
        semantic_query="",
        keyword="政务云",
        product_tags=["政务云"],
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
    import pytest
    from src.services.knowledge.blueprint_search_service import BlueprintSearchValidationError

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_search_service.py -v`

Expected: FAIL

- [ ] **Step 3: Implement core search logic**

```python
# backend/src/services/knowledge/blueprint_search_service.py
from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from sqlalchemy import String, and_, cast
from sqlalchemy.orm import Session

from src.models.blueprint_embedding import BlueprintEmbedding
from src.models.knowledge_blueprint import BlueprintStatus, KnowledgeBlueprint
from src.services.knowledge.blueprint_index_text import build_highlights, keyword_score
from src.services.knowledge.blueprint_service import _apply_tag_filter


class BlueprintSearchValidationError(Exception):
    pass


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _normalize_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    max_score = max(scores)
    if max_score <= 0:
        return [0.0 for _ in scores]
    return [score / max_score for score in scores]


def search_blueprints(
    db: Session,
    *,
    kb_id: UUID,
    semantic_query: str,
    keyword: str,
    product_tags: list[str],
    industry_tags: list[str],
    scenario_tags: list[str],
    vector_weight: float,
    keyword_weight: float,
    top_k: int,
    query_vector: list[float] | None,
) -> dict[str, Any]:
    semantic = semantic_query.strip()
    kw = keyword.strip()
    if not semantic and not kw:
        raise BlueprintSearchValidationError("semantic_query and keyword cannot both be empty")

    query = db.query(KnowledgeBlueprint, BlueprintEmbedding).outerjoin(
        BlueprintEmbedding,
        BlueprintEmbedding.blueprint_id == KnowledgeBlueprint.blueprint_id,
    ).filter(
        KnowledgeBlueprint.kb_id == kb_id,
        KnowledgeBlueprint.status == BlueprintStatus.active,
    )
    query = _apply_tag_filter(query, KnowledgeBlueprint.product_tags, product_tags)
    query = _apply_tag_filter(query, KnowledgeBlueprint.industry_tags, industry_tags)
    query = _apply_tag_filter(query, KnowledgeBlueprint.scenario_tags, scenario_tags)

    rows = query.all()
    candidates_scanned = len(rows)

    raw_keyword_scores: list[float] = []
    raw_vector_scores: list[float] = []
    prepared: list[tuple[KnowledgeBlueprint, BlueprintEmbedding | None, float, float]] = []

    for blueprint, embedding_row in rows:
        search_text = embedding_row.search_text if embedding_row else ""
        k_score = keyword_score(
            keyword=kw,
            name=blueprint.name,
            description=blueprint.description,
            search_text=search_text,
        ) if kw else 0.0
        v_score = 0.0
        if query_vector and embedding_row and embedding_row.embedding:
            vec = embedding_row.embedding
            if isinstance(vec, list):
                v_score = max(0.0, _cosine_similarity(vec, query_vector))
        raw_keyword_scores.append(k_score)
        raw_vector_scores.append(v_score)
        prepared.append((blueprint, embedding_row, k_score, v_score))

    norm_k = _normalize_scores(raw_keyword_scores)
    norm_v = _normalize_scores(raw_vector_scores)

    items: list[dict[str, Any]] = []
    for idx, (blueprint, embedding_row, k_score, v_score) in enumerate(prepared):
        final = vector_weight * norm_v[idx] + keyword_weight * norm_k[idx]
        if final <= 0:
            continue
        highlights = build_highlights(
            keyword=kw,
            name=blueprint.name,
            description=blueprint.description,
            search_text=embedding_row.search_text if embedding_row else "",
        ) if kw else []
        items.append({
            "blueprint_id": str(blueprint.blueprint_id),
            "name": blueprint.name,
            "description": blueprint.description,
            "product_tags": blueprint.product_tags or [],
            "industry_tags": blueprint.industry_tags or [],
            "scenario_tags": blueprint.scenario_tags or [],
            "source_chapter_title": blueprint.source_chapter_title,
            "version": blueprint.version,
            "updated_at": blueprint.updated_at.isoformat() if blueprint.updated_at else None,
            "embedding_status": embedding_row.embedding_status if embedding_row else "pending",
            "score": round(final, 4),
            "score_detail": {
                "vector_score": round(v_score, 4),
                "keyword_score": round(k_score, 4),
                "vector_weight": vector_weight,
                "keyword_weight": keyword_weight,
            },
            "highlights": highlights,
        })

    items.sort(key=lambda item: item["score"], reverse=True)
    top_k = max(1, min(int(top_k or 10), 50))
    items = items[:top_k]

    vector_enabled = query_vector is not None
    return {
        "items": items,
        "total": len(items),
        "search_meta": {
            "vector_enabled": vector_enabled,
            "keyword_enabled": bool(kw),
            "candidates_scanned": candidates_scanned,
        },
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_search_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_search_service.py backend/tests/unit/test_blueprint_search_service.py
git commit -m "feat: add blueprint hybrid search service"
```

---

## Task 6: LLM 查询解析服务

**Files:**
- Create: `backend/src/services/knowledge/blueprint_query_parse_service.py`
- Create: `backend/tests/unit/test_blueprint_query_parse_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_blueprint_query_parse_service.py
from src.services.knowledge.blueprint_query_parse_service import parse_search_query_response

MOCK_JSON = """
{
  "semantic_query": "政务云 技术架构 章节",
  "keyword": "政务云 技术架构",
  "product_tags": ["政务云"],
  "industry_tags": ["政府"],
  "scenario_tags": []
}
"""


def test_parse_search_query_response_valid():
    result = parse_search_query_response(MOCK_JSON)
    assert result["semantic_query"] == "政务云 技术架构 章节"
    assert result["keyword"] == "政务云 技术架构"
    assert result["product_tags"] == ["政务云"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_query_parse_service.py -v`

Expected: FAIL

- [ ] **Step 3: Implement**

```python
# backend/src/services/knowledge/blueprint_query_parse_service.py
from __future__ import annotations

import json
import logging
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是目录蓝图检索助手。将用户的自然语言搜索意图拆分为结构化 JSON。\n"
    "字段：semantic_query（用于向量语义检索，提炼核心概念）、"
    "keyword（用于关键词匹配，2-5个词）、"
    "product_tags、industry_tags、scenario_tags（数组，无则空数组）。\n"
    "只返回 JSON，不要 markdown。"
)


class SearchParseTimeoutError(Exception):
    pass


class SearchParseFailedError(Exception):
    pass


def parse_search_query_response(raw: str) -> dict[str, Any]:
    parsed = _parse_llm_json(raw)
    if parsed is None:
        raise SearchParseFailedError("invalid llm json")
    semantic_query = str(parsed.get("semantic_query") or "").strip()
    keyword = str(parsed.get("keyword") or "").strip()
    if not semantic_query and not keyword:
        raise SearchParseFailedError("semantic_query and keyword missing")
    return {
        "semantic_query": semantic_query,
        "keyword": keyword,
        "product_tags": _as_str_list(parsed.get("product_tags")),
        "industry_tags": _as_str_list(parsed.get("industry_tags")),
        "scenario_tags": _as_str_list(parsed.get("scenario_tags")),
    }


def parse_search_query(*, query: str) -> dict[str, Any]:
    if not settings.llm_enabled:
        raise SearchParseFailedError("llm not configured")
    text = query.strip()
    if not text:
        raise SearchParseFailedError("query empty")
    if len(text) > settings.blueprint_search_parse_query_max:
        raise SearchParseFailedError("query too long")
    raw = _chat_with_timeout(user_prompt=text)
    return parse_search_query_response(raw)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _chat_with_timeout(*, user_prompt: str) -> str:
    model = settings.blueprint_search_parse_model
    timeout_sec = settings.blueprint_search_parse_timeout_sec
    url = f"{settings.resolved_llm_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"])
    except TimeoutError as exc:
        raise SearchParseTimeoutError("search parse timed out") from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise SearchParseTimeoutError("search parse timed out") from exc
        raise SearchParseFailedError("llm request failed") from exc
    except (urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise SearchParseFailedError("llm response malformed") from exc
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("blueprint search parse llm elapsed_ms=%.1f model=%s", elapsed_ms, model)


def _parse_llm_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
```

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_blueprint_query_parse_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/blueprint_query_parse_service.py \
  backend/tests/unit/test_blueprint_query_parse_service.py
git commit -m "feat: add blueprint search query parse service"
```

---

## Task 7: Pydantic Schemas

**Files:**
- Modify: `backend/src/api/schemas/blueprints.py`

- [ ] **Step 1: Add schemas**

```python
# backend/src/api/schemas/blueprints.py — append:

class ParseSearchQueryRequest(BaseModel):
    query: str = Field(min_length=1)


class ParseSearchQueryResponse(BaseModel):
    semantic_query: str
    keyword: str
    product_tags: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    scenario_tags: list[str] = Field(default_factory=list)


class BlueprintSearchRequest(BaseModel):
    semantic_query: str = ""
    keyword: str = ""
    product_tags: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    scenario_tags: list[str] = Field(default_factory=list)
    vector_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    keyword_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    top_k: int = Field(default=10, ge=1, le=50)


class BlueprintSearchHighlight(BaseModel):
    field: str
    snippet: str


class BlueprintSearchItem(BaseModel):
    blueprint_id: str
    name: str
    description: str | None = None
    product_tags: list[str] = Field(default_factory=list)
    industry_tags: list[str] = Field(default_factory=list)
    scenario_tags: list[str] = Field(default_factory=list)
    source_chapter_title: str | None = None
    version: int
    updated_at: str | None = None
    embedding_status: str
    score: float
    score_detail: dict[str, float]
    highlights: list[BlueprintSearchHighlight] = Field(default_factory=list)


class BlueprintSearchResponse(BaseModel):
    items: list[BlueprintSearchItem]
    total: int
    search_meta: dict[str, object]
```

- [ ] **Step 2: Verify import**

Run: `cd backend && ../.venv/bin/python -c "from src.api.schemas.blueprints import BlueprintSearchRequest; print(BlueprintSearchRequest())"`

Expected: no error

- [ ] **Step 3: Commit**

```bash
git add backend/src/api/schemas/blueprints.py
git commit -m "feat: add blueprint semantic search pydantic schemas"
```

---

## Task 8: API 路由与索引钩子

**Files:**
- Modify: `backend/src/api/routes/blueprints.py`

- [ ] **Step 1: Write integration tests (failing)**

```python
# backend/tests/integration/test_blueprint_search_api.py
from uuid import uuid4

MOCK_PARSE_JSON = {
    "semantic_query": "政务云 架构",
    "keyword": "政务云",
    "product_tags": ["政务云"],
    "industry_tags": [],
    "scenario_tags": [],
}


def test_parse_search_query_api(client, seeded_kb, monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.blueprints.parse_search_query",
        lambda **_: MOCK_PARSE_JSON,
    )
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/parse-search-query",
        json={"query": "找政务云架构蓝图"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["keyword"] == "政务云"


def test_search_api_requires_query(client, seeded_kb):
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/blueprints/search",
        json={"semantic_query": "", "keyword": ""},
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_blueprint_search_api.py -v`

Expected: FAIL (404 route not found)

- [ ] **Step 3: Add routes and background hooks**

In `backend/src/api/routes/blueprints.py`:

1. Import `BackgroundTasks`, new schemas, services.
2. Add background helper:

```python
def _embed_blueprint_in_background(blueprint_id: UUID) -> None:
    from src.db.session import SessionLocal
    from src.services.knowledge.blueprint_embedding_task import embed_blueprint

    db = SessionLocal()
    try:
        embed_blueprint(db, blueprint_id)
    finally:
        db.close()
```

3. Update `create_blueprint_api` / `update_blueprint_api` signatures to accept `background_tasks: BackgroundTasks` and call `background_tasks.add_task(_embed_blueprint_in_background, row.blueprint_id)` after commit.

4. Add endpoints:

```python
@router.post("/parse-search-query")
def parse_search_query_api(...):
    ...

@router.post("/search")
def search_blueprints_api(...):
    # embed semantic_query via EmbeddingClient when configured
    # call search_blueprints(...)
    ...

@router.post("/index/rebuild")
def rebuild_blueprint_index_api(..., background_tasks: BackgroundTasks):
    # queue rebuild_blueprints_for_kb in background
    ...
```

5. Extend `_serialize_blueprint_item` to include `embedding_status` via `get_blueprint_embedding_status`.

- [ ] **Step 4: Run integration tests**

Run: `cd backend && ../.venv/bin/pytest tests/integration/test_blueprint_search_api.py tests/integration/test_blueprint_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/blueprints.py backend/tests/integration/test_blueprint_search_api.py
git commit -m "feat: add blueprint semantic search API routes"
```

---

## Task 9: 前端 API Client

**Files:**
- Modify: `frontend/src/services/blueprints.ts`

- [ ] **Step 1: Add types and functions**

```typescript
export interface ParseSearchQueryRequest {
  query: string;
}

export interface ParseSearchQueryResult {
  semantic_query: string;
  keyword: string;
  product_tags: string[];
  industry_tags: string[];
  scenario_tags: string[];
}

export interface BlueprintSearchParams {
  semantic_query?: string;
  keyword?: string;
  product_tags?: string[];
  industry_tags?: string[];
  scenario_tags?: string[];
  vector_weight?: number;
  keyword_weight?: number;
  top_k?: number;
}

export interface BlueprintSearchHighlight {
  field: string;
  snippet: string;
}

export interface BlueprintSearchItem extends BlueprintListItem {
  score: number;
  score_detail: {
    vector_score: number;
    keyword_score: number;
    vector_weight: number;
    keyword_weight: number;
  };
  highlights: BlueprintSearchHighlight[];
  embedding_status?: string;
}

export interface BlueprintSearchResult {
  items: BlueprintSearchItem[];
  total: number;
  search_meta: {
    vector_enabled: boolean;
    keyword_enabled: boolean;
    candidates_scanned: number;
  };
}

export async function parseBlueprintSearchQuery(
  kbId: string,
  body: ParseSearchQueryRequest,
): Promise<ParseSearchQueryResult> {
  return apiRequest<ParseSearchQueryResult>(
    `/api/v1/kbs/${kbId}/blueprints/parse-search-query`,
    { method: "POST", body },
  );
}

export async function searchBlueprints(
  kbId: string,
  body: BlueprintSearchParams,
): Promise<BlueprintSearchResult> {
  return apiRequest<BlueprintSearchResult>(
    `/api/v1/kbs/${kbId}/blueprints/search`,
    { method: "POST", body },
  );
}

export async function rebuildBlueprintIndex(
  kbId: string,
): Promise<{ queued: number; message: string }> {
  return apiRequest<{ queued: number; message: string }>(
    `/api/v1/kbs/${kbId}/blueprints/index/rebuild`,
    { method: "POST" },
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npm run build`

Expected: build succeeds (or `npx tsc --noEmit` if configured)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/blueprints.ts
git commit -m "feat: add blueprint semantic search API client"
```

---

## Task 10: 列表页语义搜索 UI

**Files:**
- Modify: `frontend/src/pages/Knowledge/BlueprintListPage.tsx`

- [ ] **Step 1: Add semantic search state and handlers**

Key state:

```typescript
const [semanticMode, setSemanticMode] = useState(false);
const [semanticQuery, setSemanticQuery] = useState("");
const [searchItems, setSearchItems] = useState<BlueprintSearchItem[]>([]);
```

Handler `handleSemanticSearch`:

```typescript
const handleSemanticSearch = useCallback(async () => {
  if (!selectedKbId || !semanticQuery.trim()) return;
  setLoading(true);
  try {
    const parsed = await parseBlueprintSearchQuery(selectedKbId, { query: semanticQuery.trim() });
    const result = await searchBlueprints(selectedKbId, {
      ...parsed,
      vector_weight: 0.6,
      keyword_weight: 0.4,
      top_k: 10,
    });
    setSearchItems(result.items);
    setSemanticMode(true);
  } catch (error) {
    message.error((error as Error).message);
  } finally {
    setLoading(false);
  }
}, [selectedKbId, semanticQuery]);
```

`handleExitSemanticSearch`: `setSemanticMode(false); setSearchItems([]); void refreshList();`

- [ ] **Step 2: Add UI above filter form**

```tsx
<Space style={{ width: "100%", marginBottom: 16 }} wrap>
  <Input
    style={{ minWidth: 360 }}
    value={semanticQuery}
    onChange={(e) => setSemanticQuery(e.target.value)}
    placeholder="用自然语言描述，如：政务云技术架构章节的正式风格蓝图"
    allowClear
  />
  <Button type="primary" onClick={() => void handleSemanticSearch()} loading={loading}>
    语义搜索
  </Button>
  {semanticMode ? (
    <Button onClick={handleExitSemanticSearch}>返回列表</Button>
  ) : null}
</Space>
```

- [ ] **Step 3: Conditional columns and dataSource**

When `semanticMode`:
- `dataSource={searchItems}`
- `pagination={false}`
- Append columns: 匹配分（Tooltip score_detail）、匹配摘要（`dangerouslySetInnerHTML` on first highlight）

When not `semanticMode`: existing behavior.

- [ ] **Step 4: Manual smoke test**

Run backend + frontend, open 目录蓝图列表, enter semantic query, verify table switches to results and 返回列表 restores.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Knowledge/BlueprintListPage.tsx
git commit -m "feat: add semantic search entry on blueprint list page"
```

---

## Spec Self-Review (plan vs spec)

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 蓝图级向量索引 | Task 2, 4 |
| 异步构建 + 删除级联 | Task 2 (CASCADE), Task 8 hooks |
| index/rebuild | Task 4, Task 8 |
| 关键词 + 向量 + 标量 + 权重 | Task 5, Task 7, Task 8 |
| 高亮 | Task 3, Task 5 |
| LLM 拆分 parse-search-query | Task 6, Task 8 |
| 列表页语义搜索入口 | Task 9, Task 10 |
| embedding_status 展示 | Task 8 list 扩展, Task 10 可选列 |
| 降级（无 embedding API） | Task 4 skipped, Task 5 vector_enabled=false |
| 测试计划 | Tasks 3–8, 10 |

No TBD placeholders remain in task steps.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-22-blueprint-semantic-search.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
