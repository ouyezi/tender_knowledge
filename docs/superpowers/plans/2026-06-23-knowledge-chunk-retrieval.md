# Knowledge Chunk Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付知识块手动构建索引（视觉提取 + 摘要更新 + 三向量）与语义混合检索全栈能力，并在知识浏览页提供「构建索引」按钮与语义搜索入口。

**Architecture:** 扩展 `knowledge_chunks.embedding_status` 与 `chunk_embeddings.title_embedding`；新建 `image_extraction_cache` 全局 MD5 缓存；`chunk_index_task` 编排 vision/LLM/embed 流水线；`chunk_search_service` 三向量 + 关键词混合打分；取消入库自动 embed。前端对齐 `BlueprintListPage` 语义搜索模式。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, pgvector, pytest; React 18, TypeScript, Ant Design 5.

**Design spec:** `docs/superpowers/specs/2026-06-23-knowledge-chunk-retrieval-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/config.py` | vision/index/search 配置项 |
| `.env.example` | 文档化新环境变量 |
| `backend/alembic/versions/20260623_1000_knowledge_chunk_retrieval.py` | DDL |
| `backend/src/models/knowledge_chunk.py` | `embedding_status`, `indexed_at` |
| `backend/src/models/chunk_embedding.py` | `title_embedding`, `content_hash` |
| `backend/src/models/chunk_asset.py` | `extracted_facts` |
| `backend/src/models/image_extraction_cache.py` | 全局图片 MD5 缓存 ORM |
| `backend/src/services/knowledge/chunk_index_text.py` | hash、关键词分、高亮 |
| `backend/src/services/knowledge/image_extraction_cache_service.py` | 缓存查写 |
| `backend/src/services/knowledge/image_vision_service.py` | 视觉模型调用 |
| `backend/src/services/knowledge/chunk_summary_service.py` | LLM 重写摘要/日期 |
| `backend/src/services/knowledge/chunk_index_task.py` | 索引编排 |
| `backend/src/services/knowledge/chunk_query_parse_service.py` | LLM 查询拆分 |
| `backend/src/services/knowledge/chunk_search_service.py` | 混合检索 |
| `backend/src/api/schemas/knowledge_chunks.py` | 新 Pydantic schema |
| `backend/src/api/routes/knowledge_chunks.py` | index/search/parse 端点；移除 auto-embed |
| `backend/tests/unit/test_chunk_*.py` | 各 service 单元测试 |
| `backend/tests/integration/test_knowledge_chunk_search_api.py` | API 集成测试 |
| `frontend/src/services/knowledgeChunks.ts` | API client |
| `frontend/src/constants/knowledgeChunkMeta.ts` | embedding_status 枚举扩展 |
| `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx` | 构建索引 + 语义搜索 UI |

---

## Task 1: 配置项

**Files:**
- Modify: `backend/src/config.py`
- Modify: `.env.example`
- Create: `backend/tests/unit/test_chunk_search_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_chunk_search_config.py
from src.config import settings


def test_knowledge_chunk_retrieval_config_defaults():
    assert settings.knowledge_vision_model == "qwen-vl-max"
    assert settings.knowledge_vision_timeout_sec == 60
    assert settings.knowledge_index_summary_model == "qwen3-max"
    assert settings.chunk_search_parse_model == "qwen3.6-flash"
    assert settings.chunk_search_title_keyword_weight == 3.0
    assert settings.chunk_search_vector_min_similarity == 0.10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_chunk_search_config.py -v`

Expected: FAIL with `AttributeError`

- [ ] **Step 3: Add settings to config.py**

```python
# backend/src/config.py — after blueprint_search_exact_match_boost:
    knowledge_vision_model: str = "qwen-vl-max"
    knowledge_vision_timeout_sec: int = 60
    knowledge_vision_max_images: int = 20
    knowledge_index_summary_model: str = "qwen3-max"
    knowledge_index_summary_timeout_sec: int = 30
    chunk_search_parse_model: str = "qwen3.6-flash"
    chunk_search_parse_timeout_sec: int = 30
    chunk_search_parse_query_max: int = 500
    chunk_search_title_keyword_weight: float = 3.0
    chunk_search_body_keyword_weight: float = 1.0
    chunk_search_vector_min_similarity: float = 0.10
    chunk_search_exact_match_boost: float = 0.35
    chunk_search_default_title_vector_weight: float = 0.25
    chunk_search_default_summary_vector_weight: float = 0.35
    chunk_search_default_content_vector_weight: float = 0.40
```

Append to `.env.example`:

```bash
KNOWLEDGE_VISION_MODEL=qwen-vl-max
KNOWLEDGE_VISION_TIMEOUT_SEC=60
KNOWLEDGE_VISION_MAX_IMAGES=20
KNOWLEDGE_INDEX_SUMMARY_MODEL=qwen3-max
KNOWLEDGE_INDEX_SUMMARY_TIMEOUT_SEC=30
CHUNK_SEARCH_PARSE_MODEL=qwen3.6-flash
CHUNK_SEARCH_PARSE_TIMEOUT_SEC=30
CHUNK_SEARCH_PARSE_QUERY_MAX=500
CHUNK_SEARCH_TITLE_KEYWORD_WEIGHT=3.0
CHUNK_SEARCH_BODY_KEYWORD_WEIGHT=1.0
CHUNK_SEARCH_VECTOR_MIN_SIMILARITY=0.10
CHUNK_SEARCH_EXACT_MATCH_BOOST=0.35
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_chunk_search_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/config.py .env.example backend/tests/unit/test_chunk_search_config.py
git commit -m "feat: add knowledge chunk retrieval config"
```

---

## Task 2: 数据模型与 Migration

**Files:**
- Modify: `backend/src/models/knowledge_chunk.py`
- Modify: `backend/src/models/chunk_embedding.py`
- Modify: `backend/src/models/chunk_asset.py`
- Create: `backend/src/models/image_extraction_cache.py`
- Create: `backend/alembic/versions/20260623_1000_knowledge_chunk_retrieval.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Extend ORM models**

```python
# knowledge_chunk.py — add after token_count field area:
    embedding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

```python
# chunk_embedding.py — add:
    title_embedding: Mapped[Any] = mapped_column(
        JSON().with_variant(Vector(1024), "postgresql"), nullable=True
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

```python
# chunk_asset.py — add:
    extracted_facts: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
```

```python
# backend/src/models/image_extraction_cache.py
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ImageExtractionCache(Base):
    __tablename__ = "image_extraction_cache"

    md5_hash: Mapped[str] = mapped_column(String(32), primary_key=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    vision_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Create migration**

```python
# backend/alembic/versions/20260623_1000_knowledge_chunk_retrieval.py
"""knowledge chunk retrieval: embedding status, title embedding, image cache

Revision ID: 20260623_1000
Revises: 20260622_1200
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260623_1000"
down_revision: str | None = "20260622_1200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_chunks",
        sa.Column("embedding_status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.add_column(
        "knowledge_chunks",
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "chunk_embeddings",
        sa.Column("title_embedding", Vector(1024), nullable=True),
    )
    op.add_column(
        "chunk_embeddings",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "chunk_assets",
        sa.Column("extracted_facts", sa.JSON(), nullable=True),
    )
    op.create_table(
        "image_extraction_cache",
        sa.Column("md5_hash", sa.String(length=32), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("extracted_facts", sa.JSON(), nullable=True),
        sa.Column("vision_model", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("md5_hash"),
    )


def downgrade() -> None:
    op.drop_table("image_extraction_cache")
    op.drop_column("chunk_assets", "extracted_facts")
    op.drop_column("chunk_embeddings", "content_hash")
    op.drop_column("chunk_embeddings", "title_embedding")
    op.drop_column("knowledge_chunks", "indexed_at")
    op.drop_column("knowledge_chunks", "embedding_status")
```

- [ ] **Step 3: Register models in `__init__.py` and `conftest.py`**

- [ ] **Step 4: Verify import**

Run: `cd backend && ../.venv/bin/python -c "from src.models.image_extraction_cache import ImageExtractionCache; print(ImageExtractionCache.__tablename__)"`

Expected: `image_extraction_cache`

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/ backend/alembic/versions/20260623_1000_knowledge_chunk_retrieval.py backend/tests/conftest.py
git commit -m "feat: add knowledge chunk retrieval schema migration"
```

---

## Task 3: 索引文本工具（hash / 关键词分 / 高亮）

**Files:**
- Create: `backend/src/services/knowledge/chunk_index_text.py`
- Create: `backend/tests/unit/test_chunk_index_text.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_chunk_index_text.py
from src.services.knowledge.chunk_index_text import (
    build_index_content_hash,
    chunk_keyword_score,
    build_chunk_highlights,
)


def test_build_index_content_hash():
    h = build_index_content_hash(title="标题", summary="摘要", content="正文")
    assert len(h) == 64


def test_chunk_keyword_score_title_weighted():
    score = chunk_keyword_score(
        keyword="ISO9001 证书",
        title="ISO9001质量管理体系证书",
        summary="",
        content="",
        title_weight=3.0,
        body_weight=1.0,
    )
    assert score > 0.5


def test_build_chunk_highlights():
    items = build_chunk_highlights(
        keyword="资质",
        title="企业资质",
        summary="含多项资质证书",
        content="",
    )
    assert items
    assert "<em>" in items[0]["snippet"]
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_chunk_index_text.py -v`

- [ ] **Step 3: Implement chunk_index_text.py**

```python
# backend/src/services/knowledge/chunk_index_text.py
from __future__ import annotations

import hashlib
import re


def build_index_content_hash(*, title: str, summary: str | None, content: str) -> str:
    text = f"{title.strip()}\n{(summary or '').strip()}\n{content.strip()}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _keyword_tokens(keyword: str) -> list[str]:
    return [token for token in re.split(r"\s+", keyword.strip()) if token]


def _token_hit_ratio(tokens: list[str], field: str) -> float:
    if not tokens or not field:
        return 0.0
    field_lower = field.lower()
    matched = sum(1 for token in tokens if token.lower() in field_lower)
    return matched / len(tokens)


def chunk_keyword_score(
    *,
    keyword: str,
    title: str,
    summary: str | None,
    content: str,
    title_weight: float = 3.0,
    body_weight: float = 1.0,
) -> float:
    tokens = _keyword_tokens(keyword)
    if not tokens:
        return 0.0
    title_ratio = _token_hit_ratio(tokens, title or "")
    body_field = f"{summary or ''}\n{content or ''}"
    body_ratio = _token_hit_ratio(tokens, body_field)
    if title_ratio >= 1.0:
        return 1.0
    weight_sum = max(title_weight + body_weight, 1e-9)
    return min(1.0, (title_weight * title_ratio + body_weight * body_ratio) / weight_sum)


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def chunk_exact_match_bonus(
    *,
    semantic_query: str,
    keyword: str,
    title: str,
    boost: float = 0.35,
) -> float:
    norm_title = _normalize_match_text(title)
    if not norm_title or boost <= 0:
        return 0.0
    for candidate in (_normalize_match_text(semantic_query), _normalize_match_text(keyword.replace(" ", ""))):
        if candidate and candidate == norm_title:
            return boost
    return 0.0


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


def build_chunk_highlights(
    *,
    keyword: str,
    title: str,
    summary: str | None,
    content: str,
) -> list[dict[str, str]]:
    highlights: list[dict[str, str]] = []
    for field, value in (("title", title), ("summary", summary or ""), ("content", content)):
        item = _highlight_text(value, keyword, field=field)
        if item:
            highlights.append(item)
    return highlights
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/chunk_index_text.py backend/tests/unit/test_chunk_index_text.py
git commit -m "feat: add chunk index text helpers"
```

---

## Task 4: 图片 MD5 缓存服务

**Files:**
- Create: `backend/src/services/knowledge/image_extraction_cache_service.py`
- Create: `backend/tests/unit/test_image_extraction_cache_service.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/unit/test_image_extraction_cache_service.py
import hashlib

from src.models.image_extraction_cache import ImageExtractionCache
from src.services.knowledge.image_extraction_cache_service import (
    compute_file_md5,
    get_or_create_extraction,
)


def test_compute_file_md5(tmp_path):
    p = tmp_path / "img.png"
    p.write_bytes(b"abc")
    assert compute_file_md5(p) == hashlib.md5(b"abc").hexdigest()


def test_get_or_create_extraction_cache_hit(db_session):
    row = ImageExtractionCache(
        md5_hash="abc123",
        caption="证书",
        ocr_text="ISO9001",
        extracted_facts={"confidence": "high"},
        vision_model="test",
    )
    db_session.add(row)
    db_session.commit()
    result = get_or_create_extraction(db_session, md5_hash="abc123", vision_fn=lambda: None)
    assert result["caption"] == "证书"
    assert result["from_cache"] is True
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Implement**

```python
# backend/src/services/knowledge/image_extraction_cache_service.py
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from src.models.image_extraction_cache import ImageExtractionCache


def compute_file_md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def get_or_create_extraction(
    db: Session,
    *,
    md5_hash: str,
    vision_fn: Callable[[], dict[str, Any] | None],
    vision_model: str,
) -> dict[str, Any]:
    row = db.get(ImageExtractionCache, md5_hash)
    if row is not None:
        return {
            "caption": row.caption,
            "ocr_text": row.ocr_text,
            "extracted_facts": row.extracted_facts,
            "from_cache": True,
        }
    extracted = vision_fn()
    if extracted is None:
        return {"caption": None, "ocr_text": None, "extracted_facts": None, "from_cache": False}
    row = ImageExtractionCache(
        md5_hash=md5_hash,
        caption=extracted.get("caption"),
        ocr_text=extracted.get("ocr_text"),
        extracted_facts=extracted.get("extracted_facts"),
        vision_model=vision_model,
    )
    db.add(row)
    db.flush()
    return {**extracted, "from_cache": False}
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

---

## Task 5: 视觉模型服务

**Files:**
- Create: `backend/src/services/knowledge/image_vision_service.py`
- Create: `backend/tests/unit/test_image_vision_service.py`

- [ ] **Step 1: Write failing test for JSON parse**

```python
# backend/tests/unit/test_image_vision_service.py
from src.services.knowledge.image_vision_service import parse_vision_response


def test_parse_vision_response_valid():
    raw = '{"caption":"证书扫描件","ocr_text":"ISO9001","extracted_facts":{"confidence":"high"}}'
    result = parse_vision_response(raw)
    assert result["caption"] == "证书扫描件"
    assert result["extracted_facts"]["confidence"] == "high"
```

- [ ] **Step 2: Implement parse + extract_image (OpenAI-compatible multimodal)**

```python
# backend/src/services/knowledge/image_vision_service.py
# parse_vision_response(raw: str) -> dict
# extract_image(*, image_path: Path) -> dict | None
# Uses settings.knowledge_vision_model, base64 image in chat/completions
# Prompt requires JSON with caption, ocr_text, extracted_facts
# On failure return None and log warning
```

- [ ] **Step 3: Run tests — expect PASS**

- [ ] **Step 4: Commit**

---

## Task 6: 摘要重写服务

**Files:**
- Create: `backend/src/services/knowledge/chunk_summary_service.py`
- Create: `backend/tests/unit/test_chunk_summary_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_chunk_summary_service.py
from src.services.knowledge.chunk_summary_service import apply_summary_update


def test_apply_summary_update_high_confidence_dates():
    chunk_fields, warnings = apply_summary_update(
        current_summary="旧摘要",
        current_issue_date=None,
        current_expire_date=None,
        llm_result={
            "summary": "新摘要",
            "issue_date": "2023-01-01",
            "expire_date": "2026-01-01",
            "date_confidence": "high",
        },
    )
    assert chunk_fields["summary"] == "新摘要"
    assert chunk_fields["issue_date"].isoformat() == "2023-01-01"
    assert not warnings


def test_apply_summary_update_low_confidence_keeps_dates():
    from datetime import date
    chunk_fields, _ = apply_summary_update(
        current_summary="旧",
        current_issue_date=date(2020, 1, 1),
        current_expire_date=None,
        llm_result={"summary": "新", "issue_date": "2023-01-01", "date_confidence": "low"},
    )
    assert chunk_fields["issue_date"].isoformat() == "2020-01-01"
```

- [ ] **Step 2: Implement `apply_summary_update` + `rewrite_chunk_summary` (LLM call)**

- [ ] **Step 3: Run tests — expect PASS**

- [ ] **Step 4: Commit**

---

## Task 7: 索引编排 `chunk_index_task`

**Files:**
- Create: `backend/src/services/knowledge/chunk_index_task.py`
- Create: `backend/tests/unit/test_chunk_index_task.py`

- [ ] **Step 1: Write failing integration-style unit test with mocks**

```python
# backend/tests/unit/test_chunk_index_task.py
# Seed chunk + image asset; monkeypatch vision/summary/embed; call index_knowledge_chunk
# Assert embedding_status=ready, summary updated, chunk_embeddings has title_embedding
```

- [ ] **Step 2: Implement index_knowledge_chunk**

核心流程：

```python
def index_knowledge_chunk(db: Session, chunk_id: int) -> str:
    chunk = db.get(KnowledgeChunk, chunk_id)
    if chunk is None:
        return "failed"
    chunk.embedding_status = "indexing"
    db.commit()

    # 1. extract images (resolve Path(settings.storage_root) / image_storage_url)
    # 2. rewrite summary via chunk_summary_service
    # 3. embed title/summary/content; upsert chunk_embeddings with content_hash
    # 4. chunk.embedding_status = "ready" | "failed" | "skipped"
    # 5. chunk.indexed_at = now() on success
    db.commit()
    return chunk.embedding_status
```

辅助函数 `_resolve_image_path(kb_id, storage_path) -> Path | None` 通过 `DocumentMediaAsset.storage_path` 或相对路径拼接。

- [ ] **Step 3: Run tests — expect PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add knowledge chunk index task pipeline"
```

---

## Task 8: 移除自动 embed + Index API + 列表字段

**Files:**
- Modify: `backend/src/api/routes/knowledge_chunks.py`
- Modify: `backend/src/api/schemas/knowledge_chunks.py`
- Modify: `backend/tests/unit/test_knowledge_embedding.py`
- Create: `backend/tests/integration/test_knowledge_chunk_index_api.py`

- [ ] **Step 1: Write failing test — create no longer embeds**

```python
# test: POST create chunk, assert embedding_status stays pending, no chunk_embeddings row
```

- [ ] **Step 2: Remove auto-embed**

```python
# knowledge_chunks.py create_knowledge_chunk_api:
# - Remove background_tasks.add_task(_embed_chunk_in_background, chunk.id)
# - Remove BackgroundTasks param if unused elsewhere in file
# - Delete _embed_chunk_in_background helper (or keep unused — prefer delete)
```

- [ ] **Step 3: Add index endpoint**

```python
@router.post("/{chunk_id}/index")
def index_knowledge_chunk_api(
    kb_id: UUID,
    chunk_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: KnowledgeBase = Depends(get_kb_or_404),
):
    row = db.query(KnowledgeChunk).filter(...).one_or_none()
    if row is None:
        return JSONResponse(status_code=404, ...)
    if row.embedding_status == "indexing":
        return JSONResponse(status_code=409, ...)
    row.embedding_status = "indexing"
    db.commit()
    background_tasks.add_task(_index_chunk_in_background, chunk_id)
    return success({"chunk_id": chunk_id, "embedding_status": "indexing"}, ...)
```

- [ ] **Step 4: Update serializers**

```python
# _serialize_chunk_list_item — add embedding_status, indexed_at
# get_knowledge_chunk_api — use row.embedding_status instead of get_embedding_status()
```

- [ ] **Step 5: Run tests — expect PASS**

- [ ] **Step 6: Commit**

---

## Task 9: 查询解析服务

**Files:**
- Create: `backend/src/services/knowledge/chunk_query_parse_service.py`
- Create: `backend/tests/unit/test_chunk_query_parse_service.py`

- [ ] **Step 1: Copy pattern from blueprint_query_parse_service with simplified prompt (semantic_query + keyword only)**

```python
_SYSTEM_PROMPT = (
    "你是知识块检索助手。将用户自然语言拆分为 JSON："
    "semantic_query（向量检索核心概念）、keyword（2-5个词，空格分隔字符串）。"
    "只返回 JSON，不要 markdown。"
)
```

- [ ] **Step 2: Tests for parse_search_query_response valid/invalid**

- [ ] **Step 3: Commit**

---

## Task 10: 混合检索服务

**Files:**
- Create: `backend/src/services/knowledge/chunk_search_service.py`
- Create: `backend/tests/unit/test_chunk_search_service.py`

- [ ] **Step 1: Write failing tests**

```python
# Seed 2 chunks: one ready with embeddings, one pending
# search_knowledge_chunks only returns ready
# Verify score ordering when keyword matches title
```

- [ ] **Step 2: Implement search_knowledge_chunks**

```python
def search_knowledge_chunks(
    db: Session,
    *,
    kb_id: UUID,
    semantic_query: str,
    keyword: str,
    vector_weight: float,
    keyword_weight: float,
    title_vector_weight: float,
    summary_vector_weight: float,
    content_vector_weight: float,
    top_k: int,
    query_vector: list[float] | None,
) -> dict[str, Any]:
    rows = (
        db.query(KnowledgeChunk, ChunkEmbedding)
        .outerjoin(ChunkEmbedding, and_(ChunkEmbedding.object_type == "chunk", ChunkEmbedding.object_id == KnowledgeChunk.id))
        .filter(KnowledgeChunk.kb_id == kb_id, KnowledgeChunk.is_latest.is_(True), KnowledgeChunk.embedding_status == "ready")
        .all()
    )
    # Python-side scoring using chunk_index_text helpers
    # Reuse _cosine_similarity, _normalize_scores, _effective_vector_scores from blueprint_search_service pattern
```

- [ ] **Step 3: Run tests — expect PASS**

- [ ] **Step 4: Commit**

---

## Task 11: Search API 端点

**Files:**
- Modify: `backend/src/api/schemas/knowledge_chunks.py`
- Modify: `backend/src/api/routes/knowledge_chunks.py`
- Create: `backend/tests/integration/test_knowledge_chunk_search_api.py`

- [ ] **Step 1: Add schemas**

```python
class ParseChunkSearchQueryRequest(BaseModel):
    query: str

class ChunkSearchRequest(BaseModel):
    semantic_query: str = ""
    keyword: str = ""
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    title_vector_weight: float = 0.25
    summary_vector_weight: float = 0.35
    content_vector_weight: float = 0.40
    top_k: int = 10
```

- [ ] **Step 2: Add routes (mirror blueprints.py error handling)**

```python
@router.post("/parse-search-query")
@router.post("/search")
```

**Route order:** 新端点 MUST 注册在 `@router.get("/{chunk_id}")` 之前，避免 path 冲突。

- [ ] **Step 3: Integration tests**

```python
# POST /parse-search-query with monkeypatch LLM
# POST /search returns empty when no ready chunks
# POST /{id}/index triggers indexing status
```

- [ ] **Step 4: Commit**

---

## Task 12: 前端 API 与浏览页 UI

**Files:**
- Modify: `frontend/src/services/knowledgeChunks.ts`
- Modify: `frontend/src/constants/knowledgeChunkMeta.ts`
- Modify: `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx`

- [ ] **Step 1: Extend knowledgeChunks.ts**

```typescript
export interface KnowledgeChunkSearchItem extends KnowledgeChunkListItem {
  score: number;
  score_detail: Record<string, number>;
  highlights: Array<{ field: string; snippet: string }>;
  summary?: string | null;
}

export async function indexKnowledgeChunk(kbId: string, chunkId: number): Promise<void> { ... }
export async function parseChunkSearchQuery(kbId: string, body: { query: string }): Promise<{ semantic_query: string; keyword: string }> { ... }
export async function searchKnowledgeChunks(kbId: string, body: ChunkSearchParams): Promise<{ items: KnowledgeChunkSearchItem[]; total: number }> { ... }
```

- [ ] **Step 2: Extend embedding_status labels**

```typescript
// knowledgeChunkMeta.ts
embedding_status: {
  pending: "待索引",
  indexing: "索引中",
  ready: "已索引",
  failed: "索引失败",
  skipped: "已跳过",
},
```

- [ ] **Step 3: KnowledgeBrowsePage changes**

参考 `BlueprintListPage.tsx`：

1. 顶部语义搜索 Input + Button + 「返回列表」
2. `semanticMode` state；搜索时覆盖 Table
3. 操作列：「构建索引」Button；`indexing` 时 loading/disabled；`ready` 显示「重新索引」
4. 新增 `embedding_status` 列 Tag
5. 搜索结果列：score、summary highlights（`dangerouslySetInnerHTML` 或简单文本 — 与蓝图一致）

- [ ] **Step 4: Manual smoke**

Run frontend dev server; 验证按钮与搜索区渲染。

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: knowledge browse index button and semantic search UI"
```

---

## Task 13: 回归与文档

**Files:**
- Modify: `backend/tests/unit/test_knowledge_embedding.py`
- Modify: `README.md`（可选，仅当有 knowledge API 段落）

- [ ] **Step 1: Update embedding tests**

`get_embedding_status` 若仍保留，改为读 `knowledge_chunks.embedding_status` 或标记 deprecated；调整测试断言。

- [ ] **Step 2: Run full backend test suite**

Run: `cd backend && ../.venv/bin/pytest tests/unit/test_chunk_index_text.py tests/unit/test_chunk_search_service.py tests/unit/test_chunk_index_task.py tests/integration/test_knowledge_chunk_search_api.py tests/integration/test_knowledge_chunk_index_api.py -v`

- [ ] **Step 3: Run frontend tests if exist**

Run: `cd frontend && npm test -- --run knowledgeChunkMeta 2>/dev/null || true`

- [ ] **Step 4: Commit**

```bash
git commit -m "test: knowledge chunk retrieval regression"
```

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| embedding_status on knowledge_chunks | Task 2, 8 |
| title_embedding + content_hash | Task 2, 7 |
| image_extraction_cache global MD5 | Task 2, 4, 5, 7 |
| extracted_facts on chunk_assets | Task 2, 7 |
| Manual index only, no auto embed | Task 8 |
| Vision structured output | Task 5, 7 |
| LLM summary + conditional dates | Task 6, 7 |
| POST /index | Task 8 |
| parse-search-query (semantic + keyword only) | Task 9, 11 |
| POST /search hybrid 3-vector | Task 10, 11 |
| Browse page UI | Task 12 |
| Only ready + is_latest in search | Task 10 |

---

## Execution Notes

- **Route registration order** in `knowledge_chunks.py`: `/parse-search-query` and `/search` before `/{chunk_id}`.
- **Image path resolution**: prefer `Path(settings.storage_root) / storage_path` where `storage_path` matches `document_media_assets.storage_path`.
- **SQLite tests**: `Vector` columns fall back to JSON; cosine similarity tests use list embeddings.
- **Do not** implement batch index or `/index/rebuild` in V1.
