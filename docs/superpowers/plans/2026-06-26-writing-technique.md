# Writing Technique (撰写技巧) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付「撰写技巧」全栈功能：从知识块 LLM 提炼写作方法论、独立表存储、列表/详情管理、知识浏览页生成入口，purge 时解绑来源并预留 embedding 索引。

**Architecture:** 独立 `writing_techniques` / `writing_technique_embeddings` 表 + `/api/v1/kbs/{kb_id}/writing-techniques/*` 路由；`generate` 自动落库 `draft`；`publish` 触发后台 embedding；前端复用目录蓝图列表/详情页模式。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL, pytest, httpx; React 18, TypeScript, Ant Design 5, Vitest.

**Design spec:** `docs/superpowers/specs/2026-06-26-writing-technique-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/alembic/versions/20260626_1000_writing_techniques.py` | 主表 + embedding 侧车 DDL |
| `backend/src/models/writing_technique.py` | 主表 ORM + `UsageMode` / `TechniqueStatus` 枚举 |
| `backend/src/models/writing_technique_embedding.py` | embedding 侧车 ORM |
| `backend/src/config.py` | `writing_technique_generate_model` / timeout |
| `backend/src/services/knowledge/writing_technique_field_utils.py` | 字段截断、confidence clamp、usage_mode 校验 |
| `backend/src/services/knowledge/writing_technique_prompt.py` | LLM system prompt 常量 |
| `backend/src/services/knowledge/writing_technique_service.py` | CRUD、bind、publish、invalidate、list |
| `backend/src/services/knowledge/writing_technique_generate_service.py` | LLM 调用 + JSON 解析 + 落库 |
| `backend/src/services/knowledge/writing_technique_index_text.py` | `search_text` 拼接 + hash |
| `backend/src/services/knowledge/writing_technique_embedding_task.py` | 发布时 embedding |
| `backend/src/api/schemas/writing_techniques.py` | Pydantic 请求/响应 |
| `backend/src/api/routes/writing_techniques.py` | REST API |
| `backend/src/services/file_import_purge_service.py` | purge 前 invalidate 撰写技巧 |
| `backend/src/main.py` | 注册 router |
| `frontend/src/services/writingTechniques.ts` | API client + 类型 |
| `frontend/src/components/WritingTechnique/*.tsx` | 表单与 ConfidenceBadge |
| `frontend/src/pages/Knowledge/WritingTechniqueListPage.tsx` | 列表 |
| `frontend/src/pages/Knowledge/WritingTechniqueDetailPage.tsx` | 详情/编辑 |
| `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx` | 「生成撰写技巧」按钮 |
| `frontend/src/App.tsx` / `frontend/src/layout/AppShell.tsx` | 路由与导航 |

---

## Task 1: LLM 配置项

**Files:**
- Modify: `backend/src/config.py`
- Create: `backend/tests/unit/test_writing_technique_config.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_writing_technique_config.py
from src.config import settings


def test_writing_technique_generate_defaults():
    assert settings.writing_technique_generate_model == "qwen-plus"
    assert settings.writing_technique_generate_timeout_sec == 30
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_config.py -v
```

Expected: FAIL `AttributeError: writing_technique_generate_model`

- [ ] **Step 3: Add settings fields**

In `backend/src/config.py` inside `class Settings`:

```python
    writing_technique_generate_model: str = "qwen-plus"
    writing_technique_generate_timeout_sec: int = 30
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_config.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/config.py backend/tests/unit/test_writing_technique_config.py
git commit -m "feat: add writing technique LLM config settings"
```

---

## Task 2: 字段工具函数

**Files:**
- Create: `backend/src/services/knowledge/writing_technique_field_utils.py`
- Create: `backend/tests/unit/test_writing_technique_field_utils.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_writing_technique_field_utils.py
from src.services.knowledge.writing_technique_field_utils import (
    clamp_confidence,
    coerce_usage_mode,
    truncate_technique_field,
)


def test_truncate_technique_field():
    assert truncate_technique_field("a" * 50, max_len=30) == "a" * 30
    assert truncate_technique_field(None, max_len=30) is None


def test_clamp_confidence():
    assert clamp_confidence(-5) == 0
    assert clamp_confidence(150) == 100
    assert clamp_confidence(72) == 72


def test_coerce_usage_mode():
    assert coerce_usage_mode("DIRECT") == "DIRECT"
    assert coerce_usage_mode("bogus") == "REFERENCE"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_field_utils.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement field utils**

```python
# backend/src/services/knowledge/writing_technique_field_utils.py
from __future__ import annotations

TITLE_MAX = 30
APPLICABLE_SCENE_MAX = 100
WRITING_SUMMARY_MAX = 200
WRITING_STRATEGY_MAX = 200

VALID_USAGE_MODES = frozenset({"DIRECT", "REFERENCE", "EXTRACT"})


def truncate_technique_field(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len]


def clamp_confidence(value: object) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def coerce_usage_mode(value: object) -> str:
    mode = str(value or "").strip().upper()
    if mode in VALID_USAGE_MODES:
        return mode
    return "REFERENCE"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_field_utils.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/writing_technique_field_utils.py \
  backend/tests/unit/test_writing_technique_field_utils.py
git commit -m "feat: add writing technique field utils"
```

---

## Task 3: 数据库 Migration + ORM Models

**Files:**
- Create: `backend/alembic/versions/20260626_1000_writing_techniques.py`
- Create: `backend/src/models/writing_technique.py`
- Create: `backend/src/models/writing_technique_embedding.py`
- Modify: `backend/src/models/__init__.py`

- [ ] **Step 1: Create Alembic migration**

`down_revision = "20260623_1000"`. 创建 `writing_techniques` 与 `writing_technique_embeddings`：

```python
# backend/alembic/versions/20260626_1000_writing_techniques.py
"""writing techniques tables

Revision ID: 20260626_1000
Revises: 20260623_1000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260626_1000"
down_revision: str | None = "20260623_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "writing_techniques",
        sa.Column("technique_id", sa.Uuid(), primary_key=True),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("applicable_scene", sa.Text(), nullable=True),
        sa.Column("writing_summary", sa.Text(), nullable=True),
        sa.Column(
            "applicable_sections",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("usage_mode", sa.String(length=20), nullable=False),
        sa.Column("recommended_outline", sa.Text(), nullable=True),
        sa.Column("writing_strategy", sa.Text(), nullable=True),
        sa.Column("must_include", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("output_requirement", sa.Text(), nullable=True),
        sa.Column("checklist", sa.Text(), nullable=True),
        sa.Column("confidence", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("source_chunk_id", sa.BigInteger(), nullable=True),
        sa.Column("source_invalid", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["knowledge_chunks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_writing_techniques_kb_id", "writing_techniques", ["kb_id"])
    op.create_index("ix_writing_techniques_kb_status", "writing_techniques", ["kb_id", "status"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_writing_techniques_kb_source_chunk
        ON writing_techniques (kb_id, source_chunk_id)
        WHERE source_chunk_id IS NOT NULL
        """
    )

    op.create_table(
        "writing_technique_embeddings",
        sa.Column("technique_id", sa.Uuid(), sa.ForeignKey("writing_techniques.technique_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kb_id", sa.Uuid(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "embedding",
            sa.JSON().with_variant(Vector(1024), "postgresql"),
            nullable=True,
        ),
        sa.Column("embedding_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_writing_technique_embeddings_kb_id", "writing_technique_embeddings", ["kb_id"])


def downgrade() -> None:
    op.drop_table("writing_technique_embeddings")
    op.drop_table("writing_techniques")
```

> 注：migration 中 `embedding` 列写法对齐 `20260622_1200_blueprint_embeddings.py`，使用 `JSON().with_variant(Vector(1024), "postgresql")`。

- [ ] **Step 2: Create ORM models**

```python
# backend/src/models/writing_technique.py
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, Integer, SmallInteger, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class UsageMode(str, enum.Enum):
    DIRECT = "DIRECT"
    REFERENCE = "REFERENCE"
    EXTRACT = "EXTRACT"


class TechniqueStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class WritingTechnique(Base):
    __tablename__ = "writing_techniques"
    __table_args__ = (
        Index("ix_writing_techniques_kb_id", "kb_id"),
        Index("ix_writing_techniques_kb_status", "kb_id", "status"),
    )

    technique_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    applicable_scene: Mapped[str | None] = mapped_column(Text, nullable=True)
    writing_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicable_sections: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    usage_mode: Mapped[UsageMode] = mapped_column(Enum(UsageMode, native_enum=False, length=20), nullable=False, default=UsageMode.REFERENCE)
    recommended_outline: Mapped[str | None] = mapped_column(Text, nullable=True)
    writing_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    must_include: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklist: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    source_chunk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_invalid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[TechniqueStatus] = mapped_column(Enum(TechniqueStatus, native_enum=False, length=20), nullable=False, default=TechniqueStatus.draft)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

```python
# backend/src/models/writing_technique_embedding.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class WritingTechniqueEmbedding(Base):
    __tablename__ = "writing_technique_embeddings"

    technique_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("writing_techniques.technique_id", ondelete="CASCADE"),
        primary_key=True,
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding: Mapped[Any] = mapped_column(JSON().with_variant(Vector(1024), "postgresql"), nullable=True)
    embedding_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3: Register models in `__init__.py`**

Add imports and `__all__` entries for `WritingTechnique`, `WritingTechniqueEmbedding`.

- [ ] **Step 4: Run migration**

```bash
cd backend && ../.venv/bin/alembic upgrade head
```

Expected: migration applies without error.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/20260626_1000_writing_techniques.py \
  backend/src/models/writing_technique.py \
  backend/src/models/writing_technique_embedding.py \
  backend/src/models/__init__.py
git commit -m "feat: add writing technique database schema and ORM models"
```

---

## Task 4: Service 层 CRUD + bind + publish

**Files:**
- Create: `backend/src/services/knowledge/writing_technique_service.py`
- Create: `backend/tests/unit/test_writing_technique_service.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_writing_technique_service.py
from uuid import uuid4

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from src.models.knowledge_chunk import KnowledgeChunk
from src.models.writing_technique import TechniqueStatus, UsageMode, WritingTechnique
from src.services.knowledge.writing_technique_service import (
    TechniqueChunkBoundError,
    TechniqueConflictError,
    TechniqueNotFoundError,
    bind_source_chunk,
    create_technique,
    get_technique_by_source,
    invalidate_techniques_by_chunk_ids,
    publish_technique,
)


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


def _seed_chunk(db_session, kb_id, *, chunk_id=101):
    row = KnowledgeChunk(
        id=chunk_id,
        kb_id=kb_id,
        knowledge_code="K-101",
        version="1.0",
        title="项目理解章节",
        content="建设背景与目标...",
        knowledge_type="method",
        doc_id=uuid4(),
        source_type="bid",
        catalog_path=[],
        primary_node_id=str(uuid4()),
        category="technical",
        tags=[],
        products=[],
        industries=[],
        customer_types=[],
        regions=[],
        content_hash="hash101",
        token_count=10,
        is_latest=True,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_create_technique_without_source(db_session, seeded_kb):
    row = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "服务方案写作技巧", "usage_mode": "DIRECT"},
    )
    db_session.commit()
    assert row.title == "服务方案写作技巧"
    assert row.source_chunk_id is None
    assert row.status == TechniqueStatus.draft


def test_bind_source_chunk_conflict(db_session, seeded_kb):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id)
    create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "A", "source_chunk_id": chunk.id},
    )
    db_session.commit()
    other = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "B"},
    )
    db_session.commit()
    with pytest.raises(TechniqueChunkBoundError):
        bind_source_chunk(db_session, kb_id=seeded_kb.kb_id, technique_id=other.technique_id, chunk_id=chunk.id)


def test_publish_increments_version(db_session, seeded_kb):
    row = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "发布测试", "usage_mode": "REFERENCE"},
    )
    db_session.commit()
    published = publish_technique(db_session, kb_id=seeded_kb.kb_id, technique_id=row.technique_id)
    db_session.commit()
    assert published.status == TechniqueStatus.published
    assert published.version == 2


def test_invalidate_techniques_by_chunk_ids(db_session, seeded_kb):
    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=202)
    row = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "待失效", "source_chunk_id": chunk.id},
    )
    db_session.commit()
    count = invalidate_techniques_by_chunk_ids(db_session, kb_id=seeded_kb.kb_id, chunk_ids=[chunk.id])
    db_session.commit()
    refreshed = db_session.get(WritingTechnique, row.technique_id)
    assert count == 1
    assert refreshed.source_chunk_id is None
    assert refreshed.source_invalid is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_service.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement service**

Implement `writing_technique_service.py` with:

- Exception classes: `TechniqueNotFoundError`, `TechniqueConflictError`, `TechniqueChunkBoundError`, `TechniqueValidationError`
- `create_technique(db, *, kb_id, payload)` — validate title non-empty; if `source_chunk_id` set, check unique via `get_technique_by_source`
- `update_technique(db, *, kb_id, technique_id, payload)` — update all editable fields; apply `truncate_technique_field` / `coerce_usage_mode` / `clamp_confidence`
- `get_technique_detail(db, *, kb_id, technique_id)` — raise `TechniqueNotFoundError` if missing
- `get_technique_by_source(db, *, kb_id, chunk_id)` — return row or None
- `list_techniques(db, *, kb_id, filters)` — keyword/tags/status/confidence/has_source/source_invalid pagination
- `delete_technique(db, *, kb_id, technique_id)`
- `bind_source_chunk(db, *, kb_id, technique_id, chunk_id)` — verify chunk exists `is_latest=True`; raise `TechniqueChunkBoundError` if another technique bound
- `publish_technique(db, *, kb_id, technique_id)` — set `status=published`, `version+=1`
- `invalidate_techniques_by_chunk_ids(db, *, kb_id, chunk_ids)` — bulk update, return count
- `apply_llm_payload(row, payload: dict)` — helper used by generate to map LLM fields onto ORM row

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_service.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/writing_technique_service.py \
  backend/tests/unit/test_writing_technique_service.py
git commit -m "feat: add writing technique CRUD and bind/publish service"
```

---

## Task 5: LLM Prompt + JSON 解析

**Files:**
- Create: `backend/src/services/knowledge/writing_technique_prompt.py`
- Create: `backend/src/services/knowledge/writing_technique_generate_service.py`
- Create: `backend/tests/unit/test_writing_technique_generate_service.py`

- [ ] **Step 1: Add prompt constant**

Create `writing_technique_prompt.py` with `SYSTEM_PROMPT` — 完整粘贴 brainstorming 确认的提示词（角色、提取原则、字段要求、JSON schema 含 `score`）。保持与设计 spec §5.3 一致。

- [ ] **Step 2: Write failing parse tests**

```python
# backend/tests/unit/test_writing_technique_generate_service.py
import json

from src.services.knowledge.writing_technique_generate_service import parse_llm_technique_payload


def test_parse_llm_technique_payload_maps_score_to_confidence():
    raw = {
        "title": "项目理解写作蓝图",
        "applicable_scene": "适用于项目理解章节",
        "writing_summary": "先背景后目标",
        "applicable_sections": ["项目理解"],
        "tags": ["项目理解", "技术方案"],
        "usage_mode": "DIRECT",
        "recommended_outline": "项目理解\n- 建设背景",
        "writing_strategy": "突出针对性",
        "must_include": "建设背景与目标",
        "notes": "",
        "output_requirement": "三级标题",
        "checklist": "是否响应招标要求",
        "score": 95,
    }
    parsed = parse_llm_technique_payload(json.dumps(raw))
    assert parsed["title"] == "项目理解写作蓝图"
    assert parsed["confidence"] == 95
    assert parsed["usage_mode"] == "DIRECT"


def test_parse_llm_technique_payload_fallback_usage_mode():
    parsed = parse_llm_technique_payload(json.dumps({"title": "x", "usage_mode": "BAD", "score": 200}))
    assert parsed["usage_mode"] == "REFERENCE"
    assert parsed["confidence"] == 100
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_generate_service.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 4: Implement parse + generate helpers**

In `writing_technique_generate_service.py`:

```python
def parse_llm_technique_payload(content: str) -> dict:
    data = json.loads(content)
    return {
        "title": truncate_technique_field(data.get("title"), max_len=TITLE_MAX) or "未命名撰写技巧",
        "applicable_scene": truncate_technique_field(data.get("applicable_scene"), max_len=APPLICABLE_SCENE_MAX) or "",
        "writing_summary": truncate_technique_field(data.get("writing_summary"), max_len=WRITING_SUMMARY_MAX) or "",
        "applicable_sections": list(data.get("applicable_sections") or []),
        "tags": list(data.get("tags") or []),
        "usage_mode": coerce_usage_mode(data.get("usage_mode")),
        "recommended_outline": data.get("recommended_outline") or "",
        "writing_strategy": truncate_technique_field(data.get("writing_strategy"), max_len=WRITING_STRATEGY_MAX) or "",
        "must_include": data.get("must_include") or "",
        "notes": data.get("notes") or "",
        "output_requirement": data.get("output_requirement") or "",
        "checklist": data.get("checklist") or "",
        "confidence": clamp_confidence(data.get("score")),
    }
```

Add `_chat_with_timeout` mirroring `blueprint_generate_service._chat_with_timeout` but using `settings.writing_technique_generate_model` and timeout.

Add exceptions: `TechniqueGenerateTimeoutError`, `TechniqueGenerateFailedError`, `TechniqueChunkNotFoundError`.

- [ ] **Step 5: Run parse tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_generate_service.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/services/knowledge/writing_technique_prompt.py \
  backend/src/services/knowledge/writing_technique_generate_service.py \
  backend/tests/unit/test_writing_technique_generate_service.py
git commit -m "feat: add writing technique LLM prompt and JSON parser"
```

---

## Task 6: Generate 落库编排

**Files:**
- Modify: `backend/src/services/knowledge/writing_technique_generate_service.py`
- Modify: `backend/tests/unit/test_writing_technique_generate_service.py`

- [ ] **Step 1: Write failing integration-style unit test**

```python
def test_generate_and_save_technique_creates_draft(db_session, seeded_kb, monkeypatch):
    from src.services.knowledge.writing_technique_generate_service import generate_and_save_technique

    chunk = _seed_chunk(db_session, seeded_kb.kb_id, chunk_id=303)
    monkeypatch.setattr(
        "src.services.knowledge.writing_technique_generate_service._chat_with_timeout",
        lambda **kwargs: json.dumps({"title": "测试", "usage_mode": "DIRECT", "score": 80}),
    )
    row = generate_and_save_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        chunk_id=chunk.id,
        confirm_overwrite=False,
    )
    db_session.commit()
    assert row.source_chunk_id == chunk.id
    assert row.status.value == "draft"
    assert row.confidence == 80
```

Add second test: existing technique without `confirm_overwrite` raises `TechniqueConflictError`; with `confirm_overwrite=True` on published row resets to draft and increments version.

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_generate_service.py::test_generate_and_save_technique_creates_draft -v
```

Expected: FAIL

- [ ] **Step 3: Implement `generate_and_save_technique`**

```python
def generate_and_save_technique(
    db: Session,
    *,
    kb_id: UUID,
    chunk_id: int,
    confirm_overwrite: bool,
) -> WritingTechnique:
    chunk = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.kb_id == kb_id, KnowledgeChunk.id == chunk_id, KnowledgeChunk.is_latest.is_(True))
        .one_or_none()
    )
    if chunk is None:
        raise TechniqueChunkNotFoundError

    existing = get_technique_by_source(db, kb_id=kb_id, chunk_id=chunk_id)
    if existing is not None and not confirm_overwrite:
        raise TechniqueConflictError

    user_prompt = f"# 输入\n\n标题：{chunk.title}\n\n内容：\n{truncate_for_llm(chunk.content)}"
    raw = _chat_with_timeout(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
    payload = parse_llm_technique_payload(raw)

    if existing is None:
        payload["source_chunk_id"] = chunk_id
        row = create_technique(db, kb_id=kb_id, payload=payload)
    else:
        apply_llm_payload(existing, payload)
        existing.source_chunk_id = chunk_id
        existing.source_invalid = False
        existing.status = TechniqueStatus.draft
        existing.version = int(existing.version) + 1
        row = existing
    db.flush()
    return row
```

- [ ] **Step 4: Run all generate service tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_generate_service.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/writing_technique_generate_service.py \
  backend/tests/unit/test_writing_technique_generate_service.py
git commit -m "feat: generate writing technique from knowledge chunk and save draft"
```

---

## Task 7: Embedding 侧车任务

**Files:**
- Create: `backend/src/services/knowledge/writing_technique_index_text.py`
- Create: `backend/src/services/knowledge/writing_technique_embedding_task.py`
- Create: `backend/tests/unit/test_writing_technique_embedding_task.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/unit/test_writing_technique_embedding_task.py
from src.services.knowledge.writing_technique_index_text import build_search_text


def test_build_search_text_joins_fields():
    detail = {
        "title": "标题",
        "applicable_scene": "场景",
        "writing_summary": "简介",
        "tags": ["标签A"],
        "writing_strategy": "策略",
        "must_include": "要点",
    }
    text = build_search_text(detail)
    assert "标题" in text
    assert "标签A" in text
    assert "策略" in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_embedding_task.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement index text + embed task**

Mirror `blueprint_embedding_task.py`:

- `build_search_text(detail)` — join fields with `\n`
- `compute_content_hash(text)` — sha256 hex
- `embed_writing_technique(db, technique_id)` — skip if embedding client not configured
- `get_writing_technique_embedding_status(db, technique_id)`

- [ ] **Step 4: Run tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_embedding_task.py -v
```

Expected: PASS (index text); embedding task test may mock client like `test_blueprint_embedding_task.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/writing_technique_index_text.py \
  backend/src/services/knowledge/writing_technique_embedding_task.py \
  backend/tests/unit/test_writing_technique_embedding_task.py
git commit -m "feat: add writing technique embedding task (reserved for pipeline)"
```

---

## Task 8: API Schemas + Routes

**Files:**
- Create: `backend/src/api/schemas/writing_techniques.py`
- Create: `backend/src/api/routes/writing_techniques.py`
- Modify: `backend/src/main.py`

- [ ] **Step 1: Create Pydantic schemas**

```python
# backend/src/api/schemas/writing_techniques.py
from pydantic import BaseModel, Field


class GenerateWritingTechniqueRequest(BaseModel):
    chunk_id: int
    confirm_overwrite: bool = False


class CreateWritingTechniqueRequest(BaseModel):
    title: str
    applicable_scene: str | None = None
    writing_summary: str | None = None
    applicable_sections: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    usage_mode: str = "REFERENCE"
    recommended_outline: str | None = None
    writing_strategy: str | None = None
    must_include: str | None = None
    notes: str | None = None
    output_requirement: str | None = None
    checklist: str | None = None
    confidence: int = 0
    source_chunk_id: int | None = None


class UpdateWritingTechniqueRequest(CreateWritingTechniqueRequest):
    pass


class BindSourceRequest(BaseModel):
    chunk_id: int


class WritingTechniqueListFilters(BaseModel):
    keyword: str | None = None
    tags: list[str] | None = None
    applicable_sections: list[str] | None = None
    usage_mode: str | None = None
    status: str | None = None
    confidence_min: int | None = None
    confidence_max: int | None = None
    source_invalid: bool | None = None
    has_source: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
```

- [ ] **Step 2: Create routes**

Implement `writing_techniques.py` router with endpoints from design spec §4. Pattern after `blueprints.py`:

- `_serialize_technique_item(row, db)` includes `embedding_status`
- `POST /generate` maps exceptions to 404/409/502/504
- `PUT /{id}/publish` calls `publish_technique` then `background_tasks.add_task(_embed_technique_in_background, technique_id)`
- Register in `main.py`: `app.include_router(writing_techniques_router)`

- [ ] **Step 3: Smoke test routes import**

```bash
cd backend && ../.venv/bin/python -c "from src.main import app; print([r.path for r in app.routes if 'writing-techniques' in getattr(r,'path','')])"
```

Expected: prints route paths including `/api/v1/kbs/{kb_id}/writing-techniques/generate`.

- [ ] **Step 4: Commit**

```bash
git add backend/src/api/schemas/writing_techniques.py \
  backend/src/api/routes/writing_techniques.py \
  backend/src/main.py
git commit -m "feat: add writing techniques REST API routes"
```

---

## Task 9: Integration API 测试

**Files:**
- Create: `backend/tests/integration/test_writing_technique_api.py`

- [ ] **Step 1: Write integration tests**

Pattern after `backend/tests/integration/test_blueprint_api.py`:

```python
def test_generate_creates_draft(client, seeded_kb, db_session, monkeypatch):
    # seed chunk
    # monkeypatch _chat_with_timeout
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/writing-techniques/generate",
        json={"chunk_id": chunk.id, "confirm_overwrite": False},
        headers={"X-Operator-Id": "admin"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "draft"
    assert data["confidence"] == 88


def test_generate_conflict_without_confirm(client, seeded_kb, monkeypatch):
    # generate once, second call without confirm_overwrite -> 409 technique_exists


def test_bind_source_conflict(client, seeded_kb, db_session):
    # two techniques, bind same chunk -> 409 chunk_already_bound


def test_get_by_source(client, seeded_kb, monkeypatch):
    # after generate, GET /by-source?chunk_id= returns technique
```

- [ ] **Step 2: Run integration tests**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_writing_technique_api.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_writing_technique_api.py
git commit -m "test: add writing technique API integration tests"
```

---

## Task 10: Purge 集成

**Files:**
- Modify: `backend/src/services/file_import_purge_service.py`
- Modify: `backend/tests/unit/test_file_import_purge_service.py`

- [ ] **Step 1: Write failing purge test**

```python
def test_purge_invalidates_writing_techniques_not_delete(db_session, seeded_kb):
    import_id, doc = _seed_import_with_chunk(db_session, seeded_kb)
    chunk_id = db_session.query(KnowledgeChunk.id).filter(KnowledgeChunk.doc_id == doc.document_id).scalar()
    technique = create_technique(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload={"title": "保留", "source_chunk_id": chunk_id},
    )
    db_session.commit()

    purge_file_import(db_session, kb_id=seeded_kb.kb_id, import_id=import_id, operator_id="admin", trace_id=None)

    refreshed = db_session.get(WritingTechnique, technique.technique_id)
    assert refreshed is not None
    assert refreshed.source_chunk_id is None
    assert refreshed.source_invalid is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py::test_purge_invalidates_writing_techniques_not_delete -v
```

Expected: FAIL (technique deleted or source still set)

- [ ] **Step 3: Wire purge service**

In `_purge_documents_for_import`, **before** deleting `knowledge_chunks`:

```python
if chunk_ids:
    _inc(
        counts,
        "writing_techniques_invalidated",
        invalidate_techniques_by_chunk_ids(db, kb_id=kb_id, chunk_ids=chunk_ids),
    )
```

Add `writing_techniques_invalidated` to `check_purge_impact` intermediate_counts (count techniques where `source_chunk_id IN chunk_ids`).

- [ ] **Step 4: Run purge tests**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_file_import_purge_service.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/file_import_purge_service.py \
  backend/tests/unit/test_file_import_purge_service.py
git commit -m "feat: invalidate writing techniques on knowledge chunk purge"
```

---

## Task 11: 前端 API Client

**Files:**
- Create: `frontend/src/services/writingTechniques.ts`

- [ ] **Step 1: Add types and API functions**

Mirror `blueprints.ts` structure:

```typescript
export type UsageMode = "DIRECT" | "REFERENCE" | "EXTRACT";
export type TechniqueStatus = "draft" | "published";

export interface WritingTechniqueDetail {
  technique_id: string;
  kb_id: string;
  title: string;
  applicable_scene: string | null;
  writing_summary: string | null;
  applicable_sections: string[];
  tags: string[];
  usage_mode: UsageMode;
  recommended_outline: string | null;
  writing_strategy: string | null;
  must_include: string | null;
  notes: string | null;
  output_requirement: string | null;
  checklist: string | null;
  confidence: number;
  source_chunk_id: number | null;
  source_invalid: boolean;
  status: TechniqueStatus;
  version: number;
  embedding_status?: string;
  created_at: string | null;
  updated_at: string | null;
}

export function generateWritingTechnique(kbId: string, chunkId: number, confirmOverwrite = false) {
  return apiRequest<WritingTechniqueDetail>(`/api/v1/kbs/${kbId}/writing-techniques/generate`, {
    method: "POST",
    body: { chunk_id: chunkId, confirm_overwrite: confirmOverwrite },
  });
}

export function getWritingTechniqueBySource(kbId: string, chunkId: number) { /* GET /by-source */ }
export function listWritingTechniques(kbId: string, params?: ListWritingTechniquesParams) { /* GET / */ }
export function getWritingTechnique(kbId: string, techniqueId: string) { /* GET /:id */ }
export function createWritingTechnique(kbId: string, body: CreateWritingTechniqueBody) { /* POST / */ }
export function updateWritingTechnique(kbId: string, techniqueId: string, body: UpdateWritingTechniqueBody) { /* PUT */ }
export function publishWritingTechnique(kbId: string, techniqueId: string) { /* PUT /publish */ }
export function bindWritingTechniqueSource(kbId: string, techniqueId: string, chunkId: number) { /* PUT /bind-source */ }
export function deleteWritingTechnique(kbId: string, techniqueId: string) { /* DELETE */ }
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run build
```

Expected: build succeeds (or `tsc --noEmit` passes).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/writingTechniques.ts
git commit -m "feat: add writing techniques frontend API client"
```

---

## Task 12: ConfidenceBadge 组件

**Files:**
- Create: `frontend/src/components/WritingTechnique/ConfidenceBadge.tsx`
- Create: `frontend/src/components/WritingTechnique/ConfidenceBadge.test.tsx`

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/components/WritingTechnique/ConfidenceBadge.test.tsx
import { render, screen } from "@testing-library/react";
import ConfidenceBadge from "./ConfidenceBadge";

it("renders high confidence as green", () => {
  render(<ConfidenceBadge value={95} />);
  expect(screen.getByText(/95/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- ConfidenceBadge.test.tsx
```

Expected: FAIL

- [ ] **Step 3: Implement component**

```tsx
import { Tag } from "antd";

const LEVELS = [
  { min: 90, color: "success", label: "成熟可用" },
  { min: 70, color: "processing", label: "参考价值" },
  { min: 50, color: "warning", label: "部分经验" },
  { min: 0, color: "error", label: "指导价值低" },
] as const;

export default function ConfidenceBadge({ value }: { value: number }) {
  const level = LEVELS.find((item) => value >= item.min) ?? LEVELS[LEVELS.length - 1];
  return <Tag color={level.color}>{value} · {level.label}</Tag>;
}
```

- [ ] **Step 4: Run test**

```bash
cd frontend && npm test -- ConfidenceBadge.test.tsx
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/WritingTechnique/ConfidenceBadge.tsx \
  frontend/src/components/WritingTechnique/ConfidenceBadge.test.tsx
git commit -m "feat: add ConfidenceBadge for writing techniques"
```

---

## Task 13: 共享表单组件

**Files:**
- Create: `frontend/src/components/WritingTechnique/WritingTechniqueMetaSection.tsx`
- Create: `frontend/src/components/WritingTechnique/WritingTechniqueGuidanceSection.tsx`
- Create: `frontend/src/components/WritingTechnique/WritingTechniqueForm.tsx`

- [ ] **Step 1: Build form sections**

`WritingTechniqueMetaSection`: title, applicable_scene, writing_summary, applicable_sections (Select tags), tags, usage_mode (Select), confidence (read-only ConfidenceBadge).

`WritingTechniqueGuidanceSection`: recommended_outline (TextArea), writing_strategy, must_include, notes, output_requirement, checklist (all TextArea).

`WritingTechniqueForm`: composes both sections; accepts `value` + `onChange` pattern like `BlueprintMetaForm`.

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/WritingTechnique/
git commit -m "feat: add writing technique form components"
```

---

## Task 14: 列表页

**Files:**
- Create: `frontend/src/pages/Knowledge/WritingTechniqueListPage.tsx`

- [ ] **Step 1: Implement list page**

Pattern after `BlueprintListPage.tsx`:

- Filters: keyword, tags, usage_mode, status, confidence_min/max
- Columns: 标题、适用场景（ellipsis）、标签、使用方式、confidence（ConfidenceBadge）、状态、来源状态、更新时间
- Actions: 查看、删除
- Header: 「新建撰写技巧」→ `createWritingTechnique` with `{ title: "未命名撰写技巧" }` then navigate to detail
- **No semantic search mode** (V1)

- [ ] **Step 2: Manual smoke**

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Knowledge/WritingTechniqueListPage.tsx
git commit -m "feat: add writing technique list page"
```

---

## Task 15: 详情页

**Files:**
- Create: `frontend/src/pages/Knowledge/WritingTechniqueDetailPage.tsx`

- [ ] **Step 1: Implement detail page**

Pattern after `BlueprintDetailPage.tsx`:

- Load `getWritingTechnique` on mount
- `source_invalid` → `<Alert type="warning" message="来源已失效" />`
- Source section: show `source_chunk_id` or「未绑定」+ Button「绑定知识块」（Modal 输入 chunk_id，V1 简单数字输入即可）
- Actions: 保存（`updateWritingTechnique`）、发布（`publishWritingTechnique`，仅 draft）、删除
- `readOnly` from `useKBContext` disables write buttons

- [ ] **Step 2: Build**

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Knowledge/WritingTechniqueDetailPage.tsx
git commit -m "feat: add writing technique detail page"
```

---

## Task 16: 知识浏览页生成入口

**Files:**
- Modify: `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx`

- [ ] **Step 1: Add generate button to actions column**

```tsx
// 在操作列 render 中增加：
<Button
  size="small"
  loading={generatingChunkId === record.id}
  disabled={readOnly}
  onClick={() => void handleGenerateTechnique(record.id)}
>
  {techniqueChunkIds.has(record.id) ? "重新生成" : "生成撰写技巧"}
</Button>
```

Implement `handleGenerateTechnique`:

1. `getWritingTechniqueBySource(kbId, chunkId)` — if exists, `Modal.confirm` 覆盖提示
2. `generateWritingTechnique(kbId, chunkId, confirmOverwrite)`
3. `navigate(/knowledge/writing-techniques/${data.technique_id})`

Optional: on list load, batch fetch `by-source` is expensive — V1 可在生成成功后把 chunkId 加入本地 `Set`; 或列表 API 后续扩展 `has_writing_technique`（本任务不扩展后端，首次显示「生成撰写技巧」，生成后变「重新生成」仅在同会话有效）。

- [ ] **Step 2: Build**

```bash
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx
git commit -m "feat: add generate writing technique action on knowledge browse"
```

---

## Task 17: 路由与导航

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

- [ ] **Step 1: Add routes**

```tsx
// App.tsx
import WritingTechniqueListPage from "./pages/Knowledge/WritingTechniqueListPage";
import WritingTechniqueDetailPage from "./pages/Knowledge/WritingTechniqueDetailPage";

<Route path="/knowledge/writing-techniques" element={<WritingTechniqueListPage />} />
<Route path="/knowledge/writing-techniques/:id" element={<WritingTechniqueDetailPage />} />
```

- [ ] **Step 2: Add nav item**

```tsx
// AppShell.tsx NAV_ITEMS
{ key: "/knowledge/writing-techniques", label: <Link to="/knowledge/writing-techniques">撰写技巧</Link> },

// getSelectedNavKey
if (pathname.startsWith("/knowledge/writing-techniques")) {
  return "/knowledge/writing-techniques";
}
```

- [ ] **Step 3: Final verification**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_writing_technique_service.py \
  tests/unit/test_writing_technique_generate_service.py \
  tests/integration/test_writing_technique_api.py -v

cd frontend && npm test -- --run && npm run build
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/layout/AppShell.tsx
git commit -m "feat: wire writing technique routes and navigation"
```

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| 独立表 + embedding 侧车 | Task 3, 7 |
| 1:1 source_chunk 唯一约束 | Task 3, 4 |
| 手动创建 source 可空 | Task 4, 8 |
| generate 自动 draft | Task 6, 8 |
| publish + embedding 预留 | Task 7, 8 |
| confidence 低分不拦截 | Task 2, 12 |
| purge 解绑 source_invalid | Task 10 |
| 已发布再生成覆盖回 draft | Task 6 |
| 列表筛选（无语义搜索） | Task 4, 8, 14 |
| 顶栏导航 + 列表 + 详情 | Task 14, 15, 17 |
| 知识浏览生成入口 | Task 16 |
| bind-source 409 | Task 4, 8, 9 |
| LLM prompt + score→confidence | Task 5, 6 |

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-26-writing-technique.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
