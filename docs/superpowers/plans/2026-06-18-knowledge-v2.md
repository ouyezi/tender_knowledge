# Knowledge V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保留旧 KU/候选流的前提下，交付知识录入 V2 工作台、浏览筛选页、三表存储（`knowledge_chunks` / `chunk_assets` / `chunk_embeddings`），并完成 tender_skills 依赖升级。

**Architecture:** 平行模块 `knowledge_v2` 服务层 + 新 API 路由 `/api/v1/kbs/{kb_id}/knowledge-chunks/*`；目录树与预览读 DB（`document_tree_nodes`）+ `content.md` + `section_slice`；本迭代不写 `retrieval_index_entries`。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, PostgreSQL 15 + pgvector, pytest; React 18, TypeScript, Ant Design; tender_skills (`doc-chunk` path dep).

**Design spec:** `docs/superpowers/specs/2026-06-18-knowledge-v2-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/alembic/versions/20260618_1000_knowledge_v2.py` | 三表 DDL |
| `backend/src/models/knowledge_chunk.py` | `KnowledgeChunk` ORM |
| `backend/src/models/chunk_asset.py` | `ChunkAsset` ORM |
| `backend/src/models/chunk_embedding.py` | `ChunkEmbedding` ORM |
| `backend/src/services/doc_chunk/section_slice.py` | 新增 `outline_nodes_from_tree_nodes` |
| `backend/src/services/knowledge_v2/entry_content_service.py` | 录入文档列表、树、预览 |
| `backend/src/services/knowledge_v2/asset_link_service.py` | 资产范围匹配与关联 |
| `backend/src/services/knowledge_v2/asset_seed_service.py` | import 时预写 `chunk_assets` |
| `backend/src/services/knowledge_v2/chunk_service.py` | 入库、版本链、去重 |
| `backend/src/services/knowledge_v2/prefill_service.py` | LLM 预填 |
| `backend/src/services/knowledge_v2/embedding_task.py` | 异步向量 |
| `backend/src/services/knowledge_v2/token_counter.py` | token 计数 |
| `backend/src/api/routes/knowledge_chunks.py` | REST API |
| `backend/src/api/schemas/knowledge_chunks.py` | Pydantic 请求/响应 |
| `backend/src/config.py` | 预填模型/超时配置 |
| `frontend/src/services/knowledgeChunks.ts` | API 客户端 |
| `frontend/src/pages/KnowledgeV2/KnowledgeEntryPage.tsx` | 三栏录入页 |
| `frontend/src/pages/KnowledgeV2/KnowledgeBrowsePage.tsx` | 筛选浏览页 |

---

## Task 1: tender_skills 依赖升级

**Files:**
- Modify: `backend/pyproject.toml`（确认 path dep 不变）
- Modify: `backend/tests/fixtures/doc_chunk_workspace_minimal/**`
- Test: `backend/tests/unit/test_doc_chunk_*.py`, `backend/tests/integration/test_doc_chunk_parse_flow.py`

> 详细步骤见 `docs/superpowers/plans/2026-06-16-doc-chunk-directory-sync.md`。本 Task 可与 Task 2+ 并行，验收前必须完成。

- [ ] **Step 1: 升级 tender_skills 并重装 backend**

```bash
cd ../tender_skills && git pull && pip install -e ".[dev]"
cd ../tender_knowledge/backend && pip install -e ".[dev]"
```

- [ ] **Step 2: 刷新 minimal fixture**

```bash
python -m doc_chunk.cli.main run /path/to/minimal.docx /tmp/ws-minimal --overwrite --skip-refine
cp -R /tmp/ws-minimal/* tests/fixtures/doc_chunk_workspace_minimal/
```

- [ ] **Step 3: 跑 doc_chunk 回归**

```bash
cd backend
pytest tests/unit/test_doc_chunk_* tests/integration/test_doc_chunk_parse_flow.py -q
```

Expected: PASS（失败则按 design spec §9 最小修复 mappers）

- [ ] **Step 4: Commit**

```bash
git add backend/tests/fixtures/doc_chunk_workspace_minimal backend/src/services/doc_chunk
git commit -m "chore: align tender_skills dependency and refresh doc_chunk fixture"
```

---

## Task 2: 配置项扩展

**Files:**
- Modify: `backend/src/config.py`
- Test: `backend/tests/unit/test_knowledge_v2_config.py`（新建）

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_knowledge_v2_config.py`:

```python
from src.config import settings


def test_knowledge_prefill_defaults():
    assert settings.knowledge_prefill_model == "qwen3-max"
    assert settings.knowledge_prefill_timeout_sec == 10
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/unit/test_knowledge_v2_config.py -v
```

Expected: FAIL `AttributeError: knowledge_prefill_model`

- [ ] **Step 3: Add settings fields**

In `backend/src/config.py`, inside `class Settings`:

```python
    knowledge_prefill_model: str = "qwen3-max"
    knowledge_prefill_timeout_sec: int = 10
    embedding_model: str = "text-embedding-v2"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_knowledge_v2_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/config.py backend/tests/unit/test_knowledge_v2_config.py
git commit -m "feat: add knowledge V2 prefill and embedding config"
```

---

## Task 3: 数据库迁移与 ORM 模型

**Files:**
- Create: `backend/alembic/versions/20260618_1000_knowledge_v2.py`
- Create: `backend/src/models/knowledge_chunk.py`
- Create: `backend/src/models/chunk_asset.py`
- Create: `backend/src/models/chunk_embedding.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/tests/conftest.py`（import 新 models）
- Test: `backend/tests/unit/test_knowledge_v2_models.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_knowledge_v2_models.py`:

```python
from sqlalchemy import inspect

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
```

- [ ] **Step 2: Run test — expect FAIL** (tables missing)

```bash
cd backend && pytest tests/unit/test_knowledge_v2_models.py -v
```

- [ ] **Step 3: Create ORM models**

`backend/src/models/knowledge_chunk.py`（核心字段，枚举用 `String` 保持与设计 spec 一致）:

```python
from __future__ import annotations

import enum
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Index, Integer, Numeric, Real, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index(
            "uq_knowledge_chunks_latest_node",
            "kb_id",
            "doc_id",
            "primary_node_id",
            unique=True,
            postgresql_where="is_latest = true",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    knowledge_code: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    doc_id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    catalog_path: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    primary_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    need_parent_context: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quote_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="full")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    tags: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    products: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    industries: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    customer_types: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    regions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    template_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variables: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclusion_rules: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    retrieval_weight: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=1.0)
    security_level: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    winning_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    edit_distance_avg: Mapped[float | None] = mapped_column(Real, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    has_children: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    children_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

`backend/src/models/chunk_asset.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ChunkAsset(Base):
    __tablename__ = "chunk_assets"
    __table_args__ = (
        Index("ix_chunk_assets_doc_range", "kb_id", "doc_id", "char_start", "char_end"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    doc_id: Mapped[Any] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    chunk_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    table_headers: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    table_rows: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    table_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allow_row_filter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    image_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_storage_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_with_text: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

`backend/src/models/chunk_embedding.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint("object_type", "object_id", name="uq_chunk_embeddings_object"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_embedding: Mapped[Any] = mapped_column(
        JSON().with_variant(Vector(1024), "postgresql"), nullable=True
    )
    summary_embedding: Mapped[Any] = mapped_column(
        JSON().with_variant(Vector(1024), "postgresql"), nullable=True
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

Register in `backend/src/models/__init__.py` and add imports in `backend/tests/conftest.py`.

- [ ] **Step 4: Create Alembic migration** `20260618_1000_knowledge_v2.py` with `down_revision = "20260614_1600"`, mirroring ORM columns + partial unique index + `vector` extension.

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_knowledge_v2_models.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/models/knowledge_chunk.py backend/src/models/chunk_asset.py \
  backend/src/models/chunk_embedding.py backend/src/models/__init__.py \
  backend/alembic/versions/20260618_1000_knowledge_v2.py \
  backend/tests/conftest.py backend/tests/unit/test_knowledge_v2_models.py
git commit -m "feat: add knowledge V2 database models and migration"
```

---

## Task 4: document_tree_nodes 章节切片适配

**Files:**
- Modify: `backend/src/services/doc_chunk/section_slice.py`
- Test: `backend/tests/unit/test_doc_chunk_section_slice.py`

- [ ] **Step 1: Write failing test** (append to `test_doc_chunk_section_slice.py`):

```python
from uuid import uuid4

from src.services.doc_chunk.section_slice import (
    outline_nodes_from_tree_nodes,
    slice_section_markdown,
)


def test_outline_nodes_from_tree_nodes_and_parent_slice():
    parent_id = uuid4()
    child_id = uuid4()
    nodes = [
        type("N", (), {
            "node_id": parent_id,
            "title": "第一章",
            "level": 1,
            "parent_id": None,
            "sort_order": 1,
        })(),
        type("N", (), {
            "node_id": child_id,
            "title": "1.1 小节",
            "level": 2,
            "parent_id": parent_id,
            "sort_order": 2,
        })(),
    ]
    content_md = "# 第一章\n\n父内容\n\n## 1.1 小节\n\n子内容\n\n## 1.2 其他\n\n忽略"
    outline = outline_nodes_from_tree_nodes(nodes)
    parent_md = slice_section_markdown(content_md, outline, str(parent_id))
    assert parent_md is not None
    assert "父内容" in parent_md
    assert "子内容" in parent_md
    assert "1.2 其他" not in parent_md
```

- [ ] **Step 2: Run — expect FAIL**

```bash
pytest tests/unit/test_doc_chunk_section_slice.py::test_outline_nodes_from_tree_nodes_and_parent_slice -v
```

- [ ] **Step 3: Implement in `section_slice.py`**

```python
def outline_nodes_from_tree_nodes(nodes: list[Any]) -> list[OutlineSliceNode]:
    return [
        OutlineSliceNode(
            node_id=str(node.node_id),
            title=str(node.title or ""),
            level=max(int(node.level or 1), 0),
            parent_id=str(node.parent_id) if getattr(node, "parent_id", None) else None,
            sort_order=int(node.sort_order or 0),
        )
        for node in nodes
    ]
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/unit/test_doc_chunk_section_slice.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/doc_chunk/section_slice.py backend/tests/unit/test_doc_chunk_section_slice.py
git commit -m "feat: slice markdown sections from document tree nodes"
```

---

## Task 5: asset_link_service（范围匹配）

**Files:**
- Create: `backend/src/services/knowledge_v2/asset_link_service.py`
- Test: `backend/tests/unit/test_knowledge_v2_asset_link.py`

- [ ] **Step 1: Write failing test**

```python
from uuid import uuid4

from src.models.chunk_asset import ChunkAsset
from src.services.knowledge_v2.asset_link_service import assets_in_range, link_assets_to_chunk


def test_assets_in_range_overlap():
    doc_id = uuid4()
    kb_id = uuid4()
    assets = [
        ChunkAsset(kb_id=kb_id, doc_id=doc_id, asset_type="image", char_start=10, char_end=20),
        ChunkAsset(kb_id=kb_id, doc_id=doc_id, asset_type="table", char_start=100, char_end=200),
    ]
    matched = assets_in_range(assets, char_start=5, char_end=25)
    assert len(matched) == 1
    assert matched[0].asset_type == "image"
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.chunk_asset import ChunkAsset


def assets_in_range(
    assets: list[ChunkAsset],
    *,
    char_start: int | None,
    char_end: int | None,
) -> list[ChunkAsset]:
    if char_start is None or char_end is None:
        return []
    result: list[ChunkAsset] = []
    for asset in assets:
        a0 = asset.char_start
        a1 = asset.char_end
        if a0 is None or a1 is None:
            continue
        if a0 < char_end and a1 > char_start:
            result.append(asset)
    return result


def link_assets_to_chunk(
    db: Session,
    *,
    kb_id,
    doc_id,
    chunk_id: int,
    char_start: int | None,
    char_end: int | None,
) -> int:
    rows = (
        db.query(ChunkAsset)
        .filter(
            ChunkAsset.kb_id == kb_id,
            ChunkAsset.doc_id == doc_id,
            ChunkAsset.chunk_id.is_(None),
        )
        .all()
    )
    matched = assets_in_range(rows, char_start=char_start, char_end=char_end)
    for row in matched:
        row.chunk_id = chunk_id
    db.flush()
    return len(matched)
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add chunk asset range matching and linking"
```

---

## Task 6: asset_seed_service（import 钩子）

**Files:**
- Create: `backend/src/services/knowledge_v2/asset_seed_service.py`
- Modify: `backend/src/services/doc_chunk/import_service.py`
- Test: `backend/tests/unit/test_knowledge_v2_asset_seed.py`

- [ ] **Step 1: Write failing test** using `doc_chunk_workspace_minimal` fixture path + mock document.

- [ ] **Step 2: Implement `seed_chunk_assets_from_workspace(db, *, kb_id, doc_id, workspace_path, image_ref_map)`**
  - 图片：读 `images/manifest.json`，`char_start/end` 来自 manifest entry（无则 skip）
  - 表格：扫 `chunks/chunk-*.json` 中 `type=table` blocks，写 `raw_markdown`
  - 全部 `chunk_id=None`

- [ ] **Step 3: Call at end of `import_workspace` after `import_media_assets`**

```python
from src.services.knowledge_v2.asset_seed_service import seed_chunk_assets_from_workspace

seed_chunk_assets_from_workspace(
    db,
    kb_id=kb_id,
    doc_id=document.document_id,
    workspace_path=loaded.root,
    image_ref_map=ctx.image_ref_map,
)
```

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: seed chunk_assets during doc_chunk import"
```

---

## Task 7: entry_content_service

**Files:**
- Create: `backend/src/services/knowledge_v2/entry_content_service.py`
- Test: `backend/tests/unit/test_knowledge_v2_entry_content.py`

- [ ] **Step 1: Write failing integration-style unit test** with db_session fixture:
  - Seed `Document` (ready) + heading `DocumentTreeNode` rows + write `content.md` via `persist_content_md`
  - Assert `get_node_preview` returns markdown containing child text for parent node
  - Assert `get_document_tree` marks `ingested=True` when `KnowledgeChunk` exists

- [ ] **Step 2: Implement key functions**

```python
def list_entry_documents(db: Session, kb_id: UUID) -> list[Document]: ...
def get_document_tree(db: Session, kb_id: UUID, doc_id: UUID) -> list[dict]: ...
def get_node_preview(db: Session, kb_id: UUID, doc_id: UUID, node_id: UUID) -> dict: ...
def build_catalog_path(nodes_by_id, node_id) -> list[dict]: ...
def infer_content_type(content_md: str, assets: list) -> str: ...
```

Use `outline_nodes_from_tree_nodes` + `slice_section_markdown`; filter tree to `DocumentTreeNodeType.heading`.

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add knowledge entry content service for tree and preview"
```

---

## Task 8: chunk_service（版本与入库）

**Files:**
- Create: `backend/src/services/knowledge_v2/chunk_service.py`
- Create: `backend/src/services/knowledge_v2/token_counter.py`
- Test: `backend/tests/unit/test_knowledge_v2_chunk_service.py`

- [ ] **Step 1: Write failing tests**

```python
def test_create_chunk_initial_version(db_session, seeded_kb):
    chunk = create_knowledge_chunk(db_session, kb_id=..., payload=..., doc_id=..., node_id=...)
    assert chunk.version == "1.0"
    assert chunk.is_latest is True


def test_create_chunk_conflict_without_force(db_session, seeded_kb):
    create_knowledge_chunk(...)
    with pytest.raises(ChunkConflictError):
        create_knowledge_chunk(..., force=False)


def test_create_chunk_force_bumps_version(db_session, seeded_kb):
    first = create_knowledge_chunk(...)
    second = create_knowledge_chunk(..., force=True)
    assert second.version == "1.1"
    assert second.previous_version_id == first.id
    db_session.refresh(first)
    assert first.is_latest is False
```

- [ ] **Step 2: Implement**

```python
class ChunkConflictError(Exception):
    def __init__(self, existing_id: int, existing_version: str):
        self.existing_id = existing_id
        self.existing_version = existing_version


def bump_version(version: str) -> str:
    major, minor = version.split(".", 1)
    return f"{major}.{int(minor) + 1}"


def create_knowledge_chunk(db, *, kb_id, payload, doc_id, primary_node_id, force: bool = False) -> KnowledgeChunk:
    existing = (
        db.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.doc_id == doc_id,
            KnowledgeChunk.primary_node_id == str(primary_node_id),
            KnowledgeChunk.is_latest.is_(True),
        )
        .one_or_none()
    )
    if existing and not force:
        raise ChunkConflictError(existing.id, existing.version)
    # compute content_hash, token_count, catalog_path, has_children, children_count
    # if existing: mark is_latest=False, version=bump_version(existing.version)
    # link_assets_to_chunk(...)
    ...
```

`token_counter.py`: use `len(text.split())` as fallback if no tiktoken; document in comment that production uses qwen-compatible counter when available.

- [ ] **Step 3: Run tests — PASS**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add knowledge chunk create and version overlay logic"
```

---

## Task 9: prefill_service

**Files:**
- Create: `backend/src/services/knowledge_v2/prefill_service.py`
- Test: `backend/tests/unit/test_knowledge_v2_prefill.py`

- [ ] **Step 1: Write failing test with monkeypatch**

```python
def test_prefill_parses_json(monkeypatch):
    monkeypatch.setattr(
        "src.services.knowledge_v2.prefill_service._chat_with_timeout",
        lambda **kw: '{"title":"T","summary":"S","knowledge_type":"fact","category":"technical","status":"draft"}',
    )
    result = prefill_knowledge_attributes(content="正文", metadata={})
    assert result["title"] == "T"
    assert result.get("warnings") is None
```

- [ ] **Step 2: Implement** with dedicated timeout via `concurrent.futures` or `urllib` timeout=`settings.knowledge_prefill_timeout_sec`; strip markdown fences from LLM JSON; validate enums with fallbacks.

- [ ] **Step 3: Timeout test** — mock slow call → returns partial dict + `warnings=["prefill_timeout"]`

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: add knowledge attribute prefill service"
```

---

## Task 10: embedding_task

**Files:**
- Create: `backend/src/services/knowledge_v2/embedding_task.py`
- Test: `backend/tests/unit/test_knowledge_v2_embedding.py`

- [ ] **Step 1: Test** — mock `EmbeddingClient.embed_text` → upsert `ChunkEmbedding` row

- [ ] **Step 2: Implement**

```python
def embed_knowledge_chunk(db: Session, chunk_id: int) -> str:
    chunk = db.get(KnowledgeChunk, chunk_id)
    if chunk is None:
        return "failed"
    client = EmbeddingClient(model=settings.embedding_model)
    if not client.is_configured:
        return "skipped"
  # embed content + summary, upsert ChunkEmbedding object_type=chunk
  # embed linked ChunkAsset rows
    return "ready"
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: add async chunk embedding task"
```

---

## Task 11: API 路由

**Files:**
- Create: `backend/src/api/schemas/knowledge_chunks.py`
- Create: `backend/src/api/routes/knowledge_chunks.py`
- Modify: `backend/src/main.py`
- Test: `backend/tests/integration/test_knowledge_v2_api.py`

- [ ] **Step 1: Write failing integration test**

```python
def test_create_and_list_knowledge_chunk(client, seeded_kb, ...):
    preview = client.get(f"/api/v1/kbs/{kb_id}/knowledge-chunks/entry/documents/{doc_id}/nodes/{node_id}/preview")
    assert preview.status_code == 200
    create = client.post(f"/api/v1/kbs/{kb_id}/knowledge-chunks/", json={...})
    assert create.status_code == 201
    listing = client.get(f"/api/v1/kbs/{kb_id}/knowledge-chunks/?keyword=...")
    assert listing.json()["data"]["total"] >= 1
```

- [ ] **Step 2: Implement router** with endpoints from design spec §6; 409 returns `error("CHUNK_EXISTS", ..., details={...})`.

- [ ] **Step 3: Register in `main.py`**

```python
from src.api.routes.knowledge_chunks import router as knowledge_chunks_router
app.include_router(knowledge_chunks_router)
```

- [ ] **Step 4: `POST /` triggers `BackgroundTasks.add_task(embed_knowledge_chunk, ...)`**

- [ ] **Step 5: Run integration tests — PASS**

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add knowledge chunks REST API"
```

---

## Task 12: 前端 API 客户端

**Files:**
- Create: `frontend/src/services/knowledgeChunks.ts`

- [ ] **Step 1: Add typed client functions**

```typescript
export interface KnowledgeChunkListItem {
  id: number;
  title: string;
  version: string;
  category: string;
  knowledge_type: string;
  status: string;
  token_count: number;
  update_time: string;
}

export async function listEntryDocuments(kbId: string) { ... }
export async function getDocumentTree(kbId: string, docId: string) { ... }
export async function getNodePreview(kbId: string, docId: string, nodeId: string) { ... }
export async function prefillKnowledgeChunk(kbId: string, body: PrefillRequest) { ... }
export async function createKnowledgeChunk(kbId: string, body: CreateRequest, force?: boolean) { ... }
export async function listKnowledgeChunks(kbId: string, params: Record<string, string>) { ... }
export async function getKnowledgeChunk(kbId: string, chunkId: number) { ... }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/knowledgeChunks.ts
git commit -m "feat: add knowledge chunks frontend API client"
```

---

## Task 13: KnowledgeEntryPage（三栏录入）

**Files:**
- Create: `frontend/src/pages/KnowledgeV2/KnowledgeEntryPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

- [ ] **Step 1: Scaffold page** with `Row`/`Col` 6-12-6 layout; document `Select`; `Tree` onSelect → load preview; right panel collapsed until「添加到知识库」.

- [ ] **Step 2: Wire prefill + form** — all editable fields from spec §2.2.3; `content` read-only `Input.TextArea`; handle 409 with `Modal.confirm` + `force: true` retry.

- [ ] **Step 3: Markdown preview** — use `react-markdown` or reuse `RichContentViewer` if compatible; render `assets` images/tables from preview response.

- [ ] **Step 4: Add routes + nav**

```tsx
// App.tsx
<Route path="/knowledge-v2/entry" element={<KnowledgeEntryPage />} />
<Route path="/knowledge-v2/browse" element={<KnowledgeBrowsePage />} />
```

```tsx
// AppShell.tsx NAV_ITEMS
{ key: "/knowledge-v2/entry", label: <Link to="/knowledge-v2/entry">知识录入 V2</Link> },
{ key: "/knowledge-v2/browse", label: <Link to="/knowledge-v2/browse">知识浏览 V2</Link> },
```

- [ ] **Step 5: Manual smoke** — select KB → doc → node → prefill → create → tree shows ingested

- [ ] **Step 6: Commit**

```bash
git commit -m "feat: add knowledge V2 entry workbench page"
```

---

## Task 14: KnowledgeBrowsePage（筛选浏览）

**Files:**
- Create: `frontend/src/pages/KnowledgeV2/KnowledgeBrowsePage.tsx`
- Create: `frontend/src/pages/KnowledgeV2/KnowledgeChunkDetailDrawer.tsx`

- [ ] **Step 1: Filter form** with all query params; debounced keyword search.

- [ ] **Step 2: Table** columns per spec; pagination.

- [ ] **Step 3: Detail drawer** — full fields, `previous_version` link, assets preview, `embedding_status`.

- [ ] **Step 4: localStorage filter presets**

```typescript
const STORAGE_KEY = (kbId: string) => `knowledge-v2-filters:${kbId}`;
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add knowledge V2 browse and filter page"
```

---

## Task 15: 端到端回归

**Files:**
- Test: `backend/tests/integration/test_knowledge_v2_flow.py`

- [ ] **Step 1: Full flow test** — import doc_chunk minimal workspace → seed assets → preview → mock prefill → create → list filter → get detail → force overwrite version `1.1`.

- [ ] **Step 2: Regression** — ensure old routes still pass

```bash
cd backend
pytest tests/integration/test_knowledge_v2_flow.py tests/contract/test_knowledge_bases_api.py -q
pytest tests/unit/test_doc_chunk_* -q
```

- [ ] **Step 3: Frontend build**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git commit -m "test: add knowledge V2 end-to-end integration coverage"
```

---

## Spec Coverage Self-Review

| Spec § | Task |
|--------|------|
| §1 tender_skills 升级 | Task 1 |
| §4 三表 DDL | Task 3 |
| §5.2 entry_content | Task 4, 7 |
| §5.3 prefill | Task 2, 9 |
| §5.4 chunk_service | Task 8 |
| §5.5 asset_seed | Task 6 |
| §5.6 embedding | Task 10 |
| §6 API | Task 11 |
| §7 前端 | Task 12–14 |
| §8 错误处理 | Task 9 (prefill), Task 11 (409/404) |
| §10 测试 | Task 15 |
| 不写 retrieval_index | 全计划无相关 Task ✓ |
| 不做 2.4 资产页 | 全计划无相关 Task ✓ |

---

## Execution Order

```text
Task 1 (parallel) ─────────────────────────────┐
Task 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 │
Task 12 → 13 → 14 (after Task 11)              │
Task 15 (last) ←───────────────────────────────┘
```

Recommended: complete Task 3 before Task 6–11; Task 4 before Task 7.
