# Knowledge Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一次性替换 `knowledge_chunks` 分类字段为配置表驱动的 taxonomy code，新增 `dynamic_knowledge_records` 独立表，并同步 API / LLM 预填 / 前端录入浏览 UI。

**Architecture:** 全局只读 `knowledge_taxonomy` 单表维护四维度枚举；静态知识块存 `block_type_code` / `application_type_code` / `business_line_codes`；动态知识独立 CRUD；块级 `expire_date` 驱动 `is_expired` 计算字段。历史 chunks TRUNCATE，不做映射。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL, pytest; React 18, TypeScript, Ant Design 5, Vitest.

**Design spec:** `docs/superpowers/specs/2026-06-28-knowledge-taxonomy-design.md`

---

## File Map

| 文件 | 职责 |
|------|------|
| `backend/src/data/knowledge_taxonomy_seed.py` | 四维度种子数据常量 |
| `backend/src/services/knowledge/taxonomy_field_utils.py` | business_line 规范化、is_expired 计算 |
| `backend/src/models/knowledge_taxonomy.py` | taxonomy ORM |
| `backend/src/models/dynamic_knowledge_record.py` | 动态知识 ORM |
| `backend/src/models/knowledge_chunk.py` | 删除旧三字段，新增 taxonomy 三字段 |
| `backend/alembic/versions/20260628_1000_knowledge_taxonomy.py` | DDL + seed + TRUNCATE chunks |
| `backend/src/services/knowledge/taxonomy_service.py` | 校验、列表、内存缓存、label 展开 |
| `backend/src/api/schemas/knowledge_taxonomy.py` | taxonomy 响应 schema |
| `backend/src/api/routes/knowledge_taxonomy.py` | 全局 taxonomy 只读 API |
| `backend/src/api/schemas/knowledge_chunks.py` | chunk 请求/筛选 schema 换字段 |
| `backend/src/api/schemas/dynamic_knowledge.py` | 动态知识 CRUD schema |
| `backend/src/api/routes/knowledge_chunks.py` | 序列化/筛选/is_expired/label 展开 |
| `backend/src/api/routes/dynamic_knowledge.py` | 动态知识 REST |
| `backend/src/services/knowledge/chunk_service.py` | 写入新字段 + taxonomy 校验 |
| `backend/src/services/knowledge/dynamic_knowledge_service.py` | 动态知识 CRUD |
| `backend/src/services/knowledge/prefill_service.py` | LLM prompt 换 taxonomy code |
| `backend/src/main.py` | 注册新 router |
| `backend/tests/helpers/chunk_payload.py` | 测试用标准 chunk payload |
| `frontend/src/services/knowledgeTaxonomy.ts` | taxonomy API client |
| `frontend/src/hooks/useKnowledgeTaxonomy.ts` | 按 dimension 加载并缓存 |
| `frontend/src/components/Knowledge/TaxonomyCascader.tsx` | block_type 两级级联选择 |
| `frontend/src/constants/knowledgeChunkMeta.ts` | 字段 label 更新 |
| `frontend/src/services/knowledgeChunks.ts` | TS 类型换字段 |
| `frontend/src/services/dynamicKnowledge.ts` | 动态知识 API |
| `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx` | 表单换 taxonomy 控件 |
| `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx` | 筛选 + 过期 Badge |
| `frontend/src/pages/Knowledge/KnowledgeChunkDetailDrawer.tsx` | 详情展示新字段 |
| `frontend/src/pages/Knowledge/DynamicKnowledgeListPage.tsx` | 动态知识列表 |
| `frontend/src/pages/Knowledge/DynamicKnowledgeDetailPage.tsx` | 动态知识表单 |
| `frontend/src/pages/Knowledge/batchIngestUtils.ts` | 批量入库 payload |
| `frontend/src/App.tsx` / `frontend/src/layout/AppShell.tsx` | 路由与导航 |

---

## Shared Test Constants

后续所有 backend 测试统一引用：

```python
# backend/tests/helpers/chunk_payload.py
from __future__ import annotations

from uuid import uuid4

DEFAULT_BLOCK_TYPE_CODE = "product_solution"
DEFAULT_APPLICATION_TYPE_CODE = "preferred_reference"
DEFAULT_BUSINESS_LINE_CODES = ["general"]


def minimal_chunk_payload(**overrides) -> dict:
    base = {
        "title": "测试知识块",
        "content": "正文内容",
        "knowledge_type": "fact",
        "content_type": "text",
        "source_type": "bid",
        "block_type_code": DEFAULT_BLOCK_TYPE_CODE,
        "application_type_code": DEFAULT_APPLICATION_TYPE_CODE,
        "business_line_codes": DEFAULT_BUSINESS_LINE_CODES,
        "status": "draft",
    }
    base.update(overrides)
    return base


def minimal_chunk_orm_kwargs(*, kb_id, doc_id, **overrides) -> dict:
    base = {
        "kb_id": kb_id,
        "knowledge_code": str(uuid4()),
        "version": "1.0",
        "is_latest": True,
        "title": "测试",
        "content": "正文",
        "knowledge_type": "fact",
        "content_type": "text",
        "doc_id": doc_id,
        "source_type": "bid",
        "primary_node_id": str(uuid4()),
        "block_type_code": DEFAULT_BLOCK_TYPE_CODE,
        "application_type_code": DEFAULT_APPLICATION_TYPE_CODE,
        "business_line_codes": DEFAULT_BUSINESS_LINE_CODES,
        "catalog_path": [],
        "tags": [],
        "industries": [],
        "customer_types": [],
        "regions": [],
        "status": "draft",
        "variables": [],
        "exclusion_rules": [],
        "content_hash": "abc123",
    }
    base.update(overrides)
    return base
```

---

## Task 1: Taxonomy 字段工具函数

**Files:**
- Create: `backend/src/services/knowledge/taxonomy_field_utils.py`
- Create: `backend/tests/unit/test_taxonomy_field_utils.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_taxonomy_field_utils.py
from datetime import date

from src.services.knowledge.taxonomy_field_utils import (
    compute_is_expired,
    normalize_business_line_codes,
)


def test_normalize_business_line_codes_empty_defaults_general():
    assert normalize_business_line_codes([]) == ["general"]
    assert normalize_business_line_codes(None) == ["general"]


def test_normalize_business_line_codes_dedupes():
    assert normalize_business_line_codes(["meal_subsidy", "meal_subsidy"]) == [
        "meal_subsidy"
    ]


def test_compute_is_expired():
    assert compute_is_expired(None) is False
    assert compute_is_expired(date(2099, 1, 1)) is False
    assert compute_is_expired(date(2000, 1, 1)) is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_taxonomy_field_utils.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement field utils**

```python
# backend/src/services/knowledge/taxonomy_field_utils.py
from __future__ import annotations

from datetime import date


def normalize_business_line_codes(codes: list[str] | None) -> list[str]:
    if not codes:
        return ["general"]
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in codes:
        code = str(raw).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized or ["general"]


def compute_is_expired(expire_date: date | None, *, today: date | None = None) -> bool:
    if expire_date is None:
        return False
    ref = today or date.today()
    return expire_date < ref
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_taxonomy_field_utils.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/taxonomy_field_utils.py \
  backend/tests/unit/test_taxonomy_field_utils.py
git commit -m "feat: add taxonomy field utils for business lines and expiry"
```

---

## Task 2: Taxonomy 种子数据模块

**Files:**
- Create: `backend/src/data/knowledge_taxonomy_seed.py`
- Create: `backend/tests/unit/test_knowledge_taxonomy_seed.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_knowledge_taxonomy_seed.py
from src.data.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS


def test_seed_has_all_dimensions():
    dimensions = {row["dimension"] for row in KNOWLEDGE_TAXONOMY_SEED_ROWS}
    assert dimensions == {"block_type", "application_type", "business_line", "dynamic_type"}


def test_block_type_has_two_levels():
    block_rows = [r for r in KNOWLEDGE_TAXONOMY_SEED_ROWS if r["dimension"] == "block_type"]
    assert any(r["level"] == 1 for r in block_rows)
    assert any(r["level"] == 2 for r in block_rows)
    child = next(r for r in block_rows if r["code"] == "qualification_sub_brand")
    assert child["parent_code"] == "qualification_document"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_taxonomy_seed.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Create seed module**

Create `backend/src/data/__init__.py` (empty) and `backend/src/data/knowledge_taxonomy_seed.py` with a list `KNOWLEDGE_TAXONOMY_SEED_ROWS: list[dict]` containing every row from design spec §4.2. Each row:

```python
{
    "dimension": "block_type",
    "code": "qualification_document",
    "parent_code": None,
    "label": "资质文件",
    "label_en": None,
    "level": 1,
    "sort_order": 10,
    "is_active": True,
    "metadata": {},
}
```

Include all rows: 20 block_type, 6 application_type, 10 business_line, 3 dynamic_type (per spec — insurance only once).

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_taxonomy_seed.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/data/__init__.py backend/src/data/knowledge_taxonomy_seed.py \
  backend/tests/unit/test_knowledge_taxonomy_seed.py
git commit -m "feat: add knowledge taxonomy seed data module"
```

---

## Task 3: ORM Models + Alembic Migration

**Files:**
- Create: `backend/src/models/knowledge_taxonomy.py`
- Create: `backend/src/models/dynamic_knowledge_record.py`
- Modify: `backend/src/models/knowledge_chunk.py`
- Modify: `backend/src/models/__init__.py`
- Create: `backend/alembic/versions/20260628_1000_knowledge_taxonomy.py`

- [ ] **Step 1: Write the failing integration test**

```python
# backend/tests/integration/test_knowledge_taxonomy_migration.py
from sqlalchemy import inspect

from src.data.knowledge_taxonomy_seed import KNOWLEDGE_TAXONOMY_SEED_ROWS
from src.models.knowledge_taxonomy import KnowledgeTaxonomy


def test_knowledge_taxonomy_table_seeded(db_session):
    count = db_session.query(KnowledgeTaxonomy).count()
    assert count == len(KNOWLEDGE_TAXONOMY_SEED_ROWS)


def test_knowledge_chunks_has_taxonomy_columns(db_session):
    columns = {col["name"] for col in inspect(db_session.bind).get_columns("knowledge_chunks")}
    assert "block_type_code" in columns
    assert "application_type_code" in columns
    assert "business_line_codes" in columns
    assert "category" not in columns
    assert "quote_mode" not in columns
    assert "products" not in columns
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_taxonomy_migration.py -v
```

Expected: FAIL (table/columns missing)

- [ ] **Step 3: Add ORM models**

`backend/src/models/knowledge_taxonomy.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Index, SmallInteger, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.session import Base


class KnowledgeTaxonomy(Base):
    __tablename__ = "knowledge_taxonomy"
    __table_args__ = (
        Index(
            "uq_knowledge_taxonomy_scope",
            text("COALESCE(kb_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "dimension",
            "code",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(128), nullable=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

`backend/src/models/dynamic_knowledge_record.py` — map all fields from spec §4.4 (`metadata` 列名避免冲突，structured_data 用 JSONB)。

Modify `backend/src/models/knowledge_chunk.py`:
- Remove `quote_mode`, `category`, `products` columns
- Add:

```python
    block_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    application_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    business_line_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
```

Update `backend/src/models/__init__.py` exports.

- [ ] **Step 4: Create Alembic migration**

`backend/alembic/versions/20260628_1000_knowledge_taxonomy.py`:

```python
"""knowledge taxonomy and dynamic knowledge

Revision ID: 20260628_1000
Revises: 20260626_1000
"""

revision = "20260628_1000"
down_revision = "20260626_1000"
```

`upgrade()` steps:
1. `op.create_table("knowledge_taxonomy", ...)`
2. `op.execute("TRUNCATE knowledge_chunks CASCADE")` — clears chunk_embeddings via FK if any
3. `op.drop_column` category, quote_mode, products from knowledge_chunks
4. `op.add_column` block_type_code, application_type_code, business_line_codes (with server_default for migration safety on empty table)
5. Create indexes per spec §4.3
6. `op.create_table("dynamic_knowledge_records", ...)`
7. Insert seed rows from `KNOWLEDGE_TAXONOMY_SEED_ROWS` via `op.bulk_insert`

`downgrade()`: reverse table creation; re-add old columns (empty defaults) — optional minimal downgrade.

Run migration:

```bash
cd backend && ../.venv/bin/alembic upgrade head
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_taxonomy_migration.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/models/knowledge_taxonomy.py \
  backend/src/models/dynamic_knowledge_record.py \
  backend/src/models/knowledge_chunk.py \
  backend/src/models/__init__.py \
  backend/alembic/versions/20260628_1000_knowledge_taxonomy.py \
  backend/tests/integration/test_knowledge_taxonomy_migration.py
git commit -m "feat: add knowledge taxonomy migration and update chunk schema"
```

---

## Task 4: Taxonomy Service（校验 + 缓存 + 列表）

**Files:**
- Create: `backend/src/services/knowledge/taxonomy_service.py`
- Create: `backend/tests/unit/test_taxonomy_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_taxonomy_service.py
import pytest

from src.services.knowledge.taxonomy_service import (
    TaxonomyValidationError,
    get_taxonomy_label,
    list_taxonomy,
    validate_application_type_code,
    validate_block_type_code,
    validate_business_line_codes,
)


def test_validate_block_type_code_accepts_seed(db_session):
    validate_block_type_code(db_session, "product_solution")


def test_validate_block_type_code_rejects_unknown(db_session):
    with pytest.raises(TaxonomyValidationError):
        validate_block_type_code(db_session, "not_a_real_code")


def test_validate_business_line_codes_normalizes_empty(db_session):
    assert validate_business_line_codes(db_session, []) == ["general"]


def test_list_taxonomy_filters_dimension(db_session):
    rows = list_taxonomy(db_session, dimension="application_type")
    codes = {row.code for row in rows}
    assert codes == {
        "fixed_reference",
        "preferred_reference",
        "composite_generation",
        "template_fill",
        "reference_rewrite",
        "fact_extraction",
    }


def test_get_taxonomy_label(db_session):
    assert get_taxonomy_label(db_session, "block_type", "product_solution") == "产品方案知识"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_taxonomy_service.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: Implement taxonomy service**

```python
# backend/src/services/knowledge/taxonomy_service.py
from __future__ import annotations

from functools import lru_cache
from typing import Iterable

from sqlalchemy.orm import Session

from src.models.knowledge_taxonomy import KnowledgeTaxonomy
from src.services.knowledge.taxonomy_field_utils import normalize_business_line_codes


class TaxonomyValidationError(ValueError):
    pass


def _base_query(db: Session):
    return db.query(KnowledgeTaxonomy).filter(
        KnowledgeTaxonomy.kb_id.is_(None),
        KnowledgeTaxonomy.is_active.is_(True),
    )


def list_taxonomy(
    db: Session,
    *,
    dimension: str | None = None,
    parent_code: str | None = None,
    active_only: bool = True,
) -> list[KnowledgeTaxonomy]:
    query = _base_query(db)
    if not active_only:
        query = db.query(KnowledgeTaxonomy).filter(KnowledgeTaxonomy.kb_id.is_(None))
    if dimension:
        query = query.filter(KnowledgeTaxonomy.dimension == dimension)
    if parent_code:
        query = query.filter(KnowledgeTaxonomy.parent_code == parent_code)
    return query.order_by(KnowledgeTaxonomy.sort_order, KnowledgeTaxonomy.code).all()


def _get_row(db: Session, *, dimension: str, code: str) -> KnowledgeTaxonomy | None:
    return (
        _base_query(db)
        .filter(
            KnowledgeTaxonomy.dimension == dimension,
            KnowledgeTaxonomy.code == code,
        )
        .one_or_none()
    )


def validate_block_type_code(db: Session, code: str) -> str:
    row = _get_row(db, dimension="block_type", code=code)
    if row is None:
        raise TaxonomyValidationError(f"invalid block_type_code: {code}")
    return code


def validate_application_type_code(db: Session, code: str) -> str:
    row = _get_row(db, dimension="application_type", code=code)
    if row is None:
        raise TaxonomyValidationError(f"invalid application_type_code: {code}")
    return code


def validate_dynamic_type_code(db: Session, code: str) -> str:
    row = _get_row(db, dimension="dynamic_type", code=code)
    if row is None:
        raise TaxonomyValidationError(f"invalid dynamic_type_code: {code}")
    return code


def validate_business_line_codes(db: Session, codes: list[str] | None) -> list[str]:
    normalized = normalize_business_line_codes(codes)
    for code in normalized:
        if _get_row(db, dimension="business_line", code=code) is None:
            raise TaxonomyValidationError(f"invalid business_line_code: {code}")
    return normalized


def get_taxonomy_label(db: Session, dimension: str, code: str) -> str | None:
    row = _get_row(db, dimension=dimension, code=code)
    return row.label if row else None


def expand_business_line_labels(db: Session, codes: Iterable[str]) -> list[str]:
    labels: list[str] = []
    for code in codes:
        label = get_taxonomy_label(db, "business_line", code)
        labels.append(label or code)
    return labels
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_taxonomy_service.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/taxonomy_service.py \
  backend/tests/unit/test_taxonomy_service.py
git commit -m "feat: add taxonomy validation and listing service"
```

---

## Task 5: Taxonomy 只读 API

**Files:**
- Create: `backend/src/api/schemas/knowledge_taxonomy.py`
- Create: `backend/src/api/routes/knowledge_taxonomy.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/integration/test_knowledge_taxonomy_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_knowledge_taxonomy_api.py
def test_list_taxonomy_block_type(client):
    resp = client.get("/api/v1/knowledge-taxonomy?dimension=block_type")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    codes = {item["code"] for item in body["data"]["items"]}
    assert "qualification_document" in codes
    assert "qualification_sub_brand" in codes
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_taxonomy_api.py -v
```

Expected: FAIL 404

- [ ] **Step 3: Implement route**

`backend/src/api/routes/knowledge_taxonomy.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.envelope import error, success
from src.db.session import get_db
from src.services.knowledge.taxonomy_service import list_taxonomy

router = APIRouter(prefix="/api/v1/knowledge-taxonomy", tags=["knowledge-taxonomy"])


def _serialize(row) -> dict:
    return {
        "code": row.code,
        "dimension": row.dimension,
        "parent_code": row.parent_code,
        "label": row.label,
        "label_en": row.label_en,
        "level": row.level,
        "sort_order": row.sort_order,
        "is_active": row.is_active,
    }


@router.get("")
def list_taxonomy_api(
    dimension: str | None = Query(default=None),
    parent_code: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    rows = list_taxonomy(
        db,
        dimension=dimension,
        parent_code=parent_code,
        active_only=active_only,
    )
    return success({"items": [_serialize(row) for row in rows]})


@router.get("/{code}")
def get_taxonomy_item_api(code: str, db: Session = Depends(get_db)):
    rows = list_taxonomy(db, active_only=True)
    match = next((row for row in rows if row.code == code), None)
    if match is None:
        return error("NOT_FOUND", "taxonomy item not found", status_code=404)
    return success(_serialize(match))
```

Register in `backend/src/main.py`:

```python
from src.api.routes.knowledge_taxonomy import router as knowledge_taxonomy_router
app.include_router(knowledge_taxonomy_router)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_taxonomy_api.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/schemas/knowledge_taxonomy.py \
  backend/src/api/routes/knowledge_taxonomy.py \
  backend/src/main.py \
  backend/tests/integration/test_knowledge_taxonomy_api.py
git commit -m "feat: add read-only knowledge taxonomy API"
```

---

## Task 6: Chunk Service + Schema 换字段

**Files:**
- Modify: `backend/src/services/knowledge/chunk_service.py`
- Modify: `backend/src/api/schemas/knowledge_chunks.py`
- Modify: `backend/tests/unit/test_knowledge_chunk_service.py`
- Create: `backend/tests/helpers/chunk_payload.py`

- [ ] **Step 1: Write the failing test**

Update `backend/tests/unit/test_knowledge_chunk_service.py` to use `minimal_chunk_payload()` from helper and assert new fields persisted:

```python
from tests.helpers.chunk_payload import minimal_chunk_payload


def test_create_knowledge_chunk_persists_taxonomy_fields(db_session, seeded_kb, seeded_document_tree):
    doc_id, node_id = seeded_document_tree
    payload = minimal_chunk_payload(
        block_type_code="ip_patent",
        application_type_code="fixed_reference",
        business_line_codes=["meal_subsidy", "general"],
    )
    chunk = create_knowledge_chunk(
        db_session,
        kb_id=seeded_kb.kb_id,
        payload=payload,
        doc_id=doc_id,
        primary_node_id=node_id,
    )
    assert chunk.block_type_code == "ip_patent"
    assert chunk.application_type_code == "fixed_reference"
    assert chunk.business_line_codes == ["meal_subsidy", "general"]
```

Add rejection test:

```python
import pytest
from src.services.knowledge.taxonomy_service import TaxonomyValidationError


def test_create_knowledge_chunk_rejects_invalid_block_type(db_session, seeded_kb, seeded_document_tree):
    doc_id, node_id = seeded_document_tree
    payload = minimal_chunk_payload(block_type_code="bogus")
    with pytest.raises(TaxonomyValidationError):
        create_knowledge_chunk(
            db_session,
            kb_id=seeded_kb.kb_id,
            payload=payload,
            doc_id=doc_id,
            primary_node_id=node_id,
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_chunk_service.py -v
```

Expected: FAIL (old fields / missing validation)

- [ ] **Step 3: Update schema and service**

In `backend/src/api/schemas/knowledge_chunks.py`:

Remove from `CreateKnowledgeChunkRequest`:
```python
    quote_mode: str = "full"
    category: str = "technical"
    products: list[str] = Field(default_factory=list)
```

Add:
```python
    block_type_code: str = "product_solution"
    application_type_code: str = "preferred_reference"
    business_line_codes: list[str] = Field(default_factory=lambda: ["general"])
```

In `KnowledgeChunkListFilters` remove `category`, `products`; add:
```python
    block_type_code: str | None = None
    application_type_code: str | None = None
    business_line_codes: list[str] | None = None
    expired_only: bool | None = None
```

In `chunk_service.create_knowledge_chunk` before constructing `KnowledgeChunk`:

```python
from src.services.knowledge.taxonomy_service import (
    validate_application_type_code,
    validate_block_type_code,
    validate_business_line_codes,
)

block_type_code = validate_block_type_code(db, str(payload.get("block_type_code") or "product_solution"))
application_type_code = validate_application_type_code(
    db, str(payload.get("application_type_code") or "preferred_reference")
)
business_line_codes = validate_business_line_codes(db, payload.get("business_line_codes"))
```

Replace old field assignments with the three new fields.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_chunk_service.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/chunk_service.py \
  backend/src/api/schemas/knowledge_chunks.py \
  backend/tests/helpers/chunk_payload.py \
  backend/tests/unit/test_knowledge_chunk_service.py
git commit -m "feat: replace chunk category fields with taxonomy codes"
```

---

## Task 7: Knowledge Chunks API（序列化 + 筛选 + is_expired）

**Files:**
- Modify: `backend/src/api/routes/knowledge_chunks.py`
- Modify: `backend/tests/integration/test_knowledge_api.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/integration/test_knowledge_api.py`:

```python
def test_create_chunk_returns_taxonomy_fields(client, kb_id, doc_tree):
    doc_id, node_id = doc_tree
    resp = client.post(
        f"/api/v1/kbs/{kb_id}/knowledge-chunks",
        json={
            "doc_id": str(doc_id),
            "primary_node_id": str(node_id),
            "title": "T",
            "content": "C",
            "knowledge_type": "fact",
            "source_type": "bid",
            "block_type_code": "official_template",
            "application_type_code": "template_fill",
            "business_line_codes": ["insurance"],
        },
    )
    assert resp.status_code == 200
    detail = client.get(f"/api/v1/kbs/{kb_id}/knowledge-chunks/{resp.json()['data']['id']}").json()
    data = detail["data"]
    assert data["block_type_code"] == "official_template"
    assert data["block_type_label"] == "官方模版"
    assert data["application_type_code"] == "template_fill"
    assert data["business_line_labels"] == ["保险"]
    assert "is_expired" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_api.py::test_create_chunk_returns_taxonomy_fields -v
```

Expected: FAIL

- [ ] **Step 3: Update routes**

In `knowledge_chunks.py`:

1. Add helper `_enrich_chunk_taxonomy(db, payload: dict, row: KnowledgeChunk) -> dict` that adds:
   - `block_type_code`, `application_type_code`, `business_line_codes`
   - `block_type_label`, `application_type_label`, `business_line_labels`
   - `is_expired` via `compute_is_expired(row.expire_date)`

2. Update `_serialize_chunk_list_item` and `_serialize_chunk_detail` — remove category/quote_mode/products; call enrich helper.

3. Update list endpoint filters:
   - Replace `filters.category` with `KnowledgeChunk.block_type_code == filters.block_type_code`
   - Replace products overlap with JSONB overlap on `business_line_codes` (Postgres: `KnowledgeChunk.business_line_codes.op("@>")(json.dumps([code]))` or Python-side filter like existing `_contains_any` but on business_line_codes)
   - Add `expired_only`: `KnowledgeChunk.expire_date.isnot(None), KnowledgeChunk.expire_date < date.today()`

4. Update `list_knowledge_chunks_api` Query params to match new filters.

- [ ] **Step 4: Run integration tests**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_knowledge_api.py -v
```

Expected: PASS (fix payload in other tests in same file using `minimal_chunk_payload` pattern)

- [ ] **Step 5: Commit**

```bash
git add backend/src/api/routes/knowledge_chunks.py \
  backend/tests/integration/test_knowledge_api.py
git commit -m "feat: expose taxonomy fields and expiry in chunk API"
```

---

## Task 8: Prefill Service 换 Taxonomy Code

**Files:**
- Modify: `backend/src/services/knowledge/prefill_service.py`
- Modify: `backend/tests/unit/test_knowledge_prefill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_normalize_prefill_maps_taxonomy_codes(monkeypatch):
    monkeypatch.setattr(
        "src.services.knowledge.prefill_service._chat_with_timeout",
        lambda **kw: '{"title":"T","block_type_code":"ip_patent","application_type_code":"fact_extraction","business_line_codes":["meal_subsidy"]}',
    )
    result = prefill_knowledge_attributes(content="x", metadata={})
    assert result["block_type_code"] == "ip_patent"
    assert result["application_type_code"] == "fact_extraction"
    assert result["business_line_codes"] == ["meal_subsidy"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_prefill.py -v
```

Expected: FAIL

- [ ] **Step 3: Update prefill_service.py**

1. Remove `_CATEGORIES`, `_QUOTE_MODES`
2. Update `_SYSTEM_PROMPT` fields to: `block_type_code, application_type_code, business_line_codes` (list valid codes inline from seed or load dynamically)
3. Update `_DEFAULT_ENUMS`:

```python
_DEFAULT_ENUMS = {
    "knowledge_type": "fact",
    "content_type": "text",
    "source_type": "bid",
    "status": "draft",
    "security_level": "internal",
    "review_status": "approved",
    "block_type_code": "product_solution",
    "application_type_code": "preferred_reference",
    "business_line_codes": ["general"],
}
```

4. In `_normalize_prefill`, parse and coerce new fields; invalid codes fall back to defaults (do not call DB — prefill is LLM-only; route layer validates on save).

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_knowledge_prefill.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/prefill_service.py \
  backend/tests/unit/test_knowledge_prefill.py
git commit -m "feat: update knowledge prefill to taxonomy codes"
```

---

## Task 9: Dynamic Knowledge 后端 CRUD

**Files:**
- Create: `backend/src/services/knowledge/dynamic_knowledge_service.py`
- Create: `backend/src/api/schemas/dynamic_knowledge.py`
- Create: `backend/src/api/routes/dynamic_knowledge.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/integration/test_dynamic_knowledge_api.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/integration/test_dynamic_knowledge_api.py
def test_dynamic_knowledge_crud(client, kb_id):
    create = client.post(
        f"/api/v1/kbs/{kb_id}/dynamic-knowledge",
        json={
            "dynamic_type_code": "brand_authorization",
            "title": "品牌授权-A",
            "content": "授权内容",
            "structured_data": {"brand": "测试品牌"},
            "business_line_codes": ["general"],
            "status": "active",
        },
    )
    assert create.status_code == 200
    record_id = create.json()["data"]["id"]

    detail = client.get(f"/api/v1/kbs/{kb_id}/dynamic-knowledge/{record_id}")
    assert detail.json()["data"]["dynamic_type_label"] == "品牌授权信息"

    client.delete(f"/api/v1/kbs/{kb_id}/dynamic-knowledge/{record_id}")
    gone = client.get(f"/api/v1/kbs/{kb_id}/dynamic-knowledge/{record_id}")
    assert gone.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_dynamic_knowledge_api.py -v
```

Expected: FAIL 404

- [ ] **Step 3: Implement service + routes**

`dynamic_knowledge_service.py` — functions: `create_record`, `get_record`, `list_records`, `update_record`, `delete_record`; use taxonomy validators; compute `content_hash` and `is_expired`.

`dynamic_knowledge.py` routes mirror writing_techniques pattern with envelope responses.

Register router in `main.py`:

```python
from src.api.routes.dynamic_knowledge import router as dynamic_knowledge_router
app.include_router(dynamic_knowledge_router)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_dynamic_knowledge_api.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/knowledge/dynamic_knowledge_service.py \
  backend/src/api/schemas/dynamic_knowledge.py \
  backend/src/api/routes/dynamic_knowledge.py \
  backend/src/main.py \
  backend/tests/integration/test_dynamic_knowledge_api.py
git commit -m "feat: add dynamic knowledge records CRUD API"
```

---

## Task 10: 更新全部 Backend 测试 Fixtures

**Files:**
- Modify: all files grep-matched with `category`, `quote_mode`, `products` in `backend/tests/`

- [ ] **Step 1: Replace ORM construction kwargs**

In each test file that constructs `KnowledgeChunk(...)`, replace:
```python
category="technical",
quote_mode="full",
products=[],
```
with:
```python
block_type_code="product_solution",
application_type_code="preferred_reference",
business_line_codes=["general"],
```

Or use `minimal_chunk_orm_kwargs()` from helper.

Affected files (minimum):
- `backend/tests/unit/test_chunk_image_assets.py`
- `backend/tests/unit/test_chunk_index_task.py`
- `backend/tests/unit/test_chunk_search_service.py`
- `backend/tests/unit/test_chunk_service_delete.py`
- `backend/tests/unit/test_file_import_purge_service.py`
- `backend/tests/unit/test_knowledge_embedding.py`
- `backend/tests/unit/test_knowledge_entry_content.py`
- `backend/tests/unit/test_writing_technique_generate_service.py`
- `backend/tests/integration/test_writing_technique_api.py`
- `backend/tests/integration/test_knowledge_flow.py`
- `backend/tests/contract/test_file_import_delete.py`

- [ ] **Step 2: Replace API JSON payloads**

In integration tests posting chunks, use fields from `minimal_chunk_payload()`.

- [ ] **Step 3: Run full backend test suite**

```bash
cd backend && ../.venv/bin/pytest -q
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: update fixtures for knowledge taxonomy schema"
```

---

## Task 11: Frontend Taxonomy API + Hook

**Files:**
- Create: `frontend/src/services/knowledgeTaxonomy.ts`
- Create: `frontend/src/hooks/useKnowledgeTaxonomy.ts`
- Create: `frontend/src/hooks/useKnowledgeTaxonomy.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/hooks/useKnowledgeTaxonomy.test.ts
import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useKnowledgeTaxonomy } from "./useKnowledgeTaxonomy";
import * as taxonomyApi from "../services/knowledgeTaxonomy";

describe("useKnowledgeTaxonomy", () => {
  it("loads items for dimension", async () => {
    vi.spyOn(taxonomyApi, "listKnowledgeTaxonomy").mockResolvedValue([
      { code: "product_solution", dimension: "block_type", parent_code: null, label: "产品方案知识", level: 1, sort_order: 0, is_active: true },
    ]);
    const { result } = renderHook(() => useKnowledgeTaxonomy("block_type"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.items).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- useKnowledgeTaxonomy.test.ts
```

Expected: FAIL module not found

- [ ] **Step 3: Implement API + hook**

`frontend/src/services/knowledgeTaxonomy.ts`:

```typescript
import { apiRequest } from "./api";

export interface TaxonomyItem {
  code: string;
  dimension: string;
  parent_code: string | null;
  label: string;
  label_en?: string | null;
  level: number;
  sort_order: number;
  is_active: boolean;
}

export async function listKnowledgeTaxonomy(params?: {
  dimension?: string;
  parent_code?: string;
}): Promise<TaxonomyItem[]> {
  const query = new URLSearchParams();
  if (params?.dimension) query.set("dimension", params.dimension);
  if (params?.parent_code) query.set("parent_code", params.parent_code);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const resp = await apiRequest<{ items: TaxonomyItem[] }>(`/api/v1/knowledge-taxonomy${suffix}`);
  return resp.items;
}
```

`frontend/src/hooks/useKnowledgeTaxonomy.ts` — load on mount, module-level cache `Map<string, TaxonomyItem[]>` keyed by dimension.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm test -- useKnowledgeTaxonomy.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/knowledgeTaxonomy.ts \
  frontend/src/hooks/useKnowledgeTaxonomy.ts \
  frontend/src/hooks/useKnowledgeTaxonomy.test.ts
git commit -m "feat: add frontend taxonomy API hook"
```

---

## Task 12: Frontend Types + Meta + Cascader 组件

**Files:**
- Modify: `frontend/src/services/knowledgeChunks.ts`
- Modify: `frontend/src/constants/knowledgeChunkMeta.ts`
- Modify: `frontend/src/constants/knowledgeChunkMeta.test.ts`
- Create: `frontend/src/components/Knowledge/TaxonomyCascader.tsx`

- [ ] **Step 1: Write the failing test**

Update `knowledgeChunkMeta.test.ts`:

```typescript
import { getFieldLabel } from "./knowledgeChunkMeta";

it("labels taxonomy fields", () => {
  expect(getFieldLabel("block_type_code")).toBe("知识块类型");
  expect(getFieldLabel("application_type_code")).toBe("应用类型");
  expect(getFieldLabel("business_line_codes")).toBe("业务线");
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm test -- knowledgeChunkMeta.test.ts
```

Expected: FAIL

- [ ] **Step 3: Update types and meta**

In `knowledgeChunks.ts` replace on interfaces:
- Remove `quote_mode`, `category`, `products`
- Add `block_type_code`, `application_type_code`, `business_line_codes`
- Add optional labels: `block_type_label?`, `application_type_label?`, `business_line_labels?`, `is_expired?`

In `knowledgeChunkMeta.ts`:
- Remove ENUM_LABELS entries for category, quote_mode
- Remove products from FIELD_LABELS or rename to business_line_codes
- Add new field labels

Create `TaxonomyCascader.tsx` — Ant Design `Cascader` built from block_type level-1/2 items; value is leaf `code` string.

- [ ] **Step 4: Run tests**

```bash
cd frontend && npm test -- knowledgeChunkMeta.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/knowledgeChunks.ts \
  frontend/src/constants/knowledgeChunkMeta.ts \
  frontend/src/constants/knowledgeChunkMeta.test.ts \
  frontend/src/components/Knowledge/TaxonomyCascader.tsx
git commit -m "feat: update frontend chunk types and taxonomy cascader"
```

---

## Task 13: 知识录入 / 浏览 / 详情 UI

**Files:**
- Modify: `frontend/src/pages/Knowledge/KnowledgeEntryPage.tsx`
- Modify: `frontend/src/pages/Knowledge/KnowledgeBrowsePage.tsx`
- Modify: `frontend/src/pages/Knowledge/KnowledgeChunkDetailDrawer.tsx`
- Modify: `frontend/src/pages/Knowledge/batchIngestUtils.ts`
- Modify: `frontend/src/pages/Knowledge/batchIngestUtils.test.ts`

- [ ] **Step 1: Update entry form**

Replace Form.Items:
- `category` → `<TaxonomyCascader />` bound to `block_type_code`
- `quote_mode` → `<Select options={applicationTypeOptions} />` for `application_type_code`
- `products` → `<Select mode="multiple" options={businessLineOptions} />` for `business_line_codes`

Update prefill mapping and submit payload.

Add `Alert` when `block_type_code` starts with `qualification_`, `financial_`, or `ip_` and `expire_date` empty.

- [ ] **Step 2: Update browse filters**

Replace category/products filters with taxonomy Selects; add expired-only Switch; show `<Tag color="warning">已过期，需更新</Tag>` when `item.is_expired`.

- [ ] **Step 3: Update detail drawer**

Show block_type_label, application_type_label, business_line_labels; warning Alert if is_expired.

- [ ] **Step 4: Update batch ingest utils/tests**

Replace old field names in `batchIngestUtils.ts` and test expectations.

- [ ] **Step 5: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Knowledge/
git commit -m "feat: update knowledge entry and browse UI for taxonomy"
```

---

## Task 14: 动态知识前端页面

**Files:**
- Create: `frontend/src/services/dynamicKnowledge.ts`
- Create: `frontend/src/pages/Knowledge/DynamicKnowledgeListPage.tsx`
- Create: `frontend/src/pages/Knowledge/DynamicKnowledgeDetailPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

- [ ] **Step 1: Implement API client**

`dynamicKnowledge.ts` — list/create/get/update/delete mirroring backend routes; types include `dynamic_type_code`, `structured_data`, `is_expired`, labels.

- [ ] **Step 2: List page**

Table columns: title, dynamic_type_label, business_line_labels, status, is_expired, update_time; filter by dynamic_type_code; link to detail.

- [ ] **Step 3: Detail page**

Form: dynamic_type Select, title, content TextArea, structured_data JSON editor (or key-value Form.List minimal), business_line multi-select, issue/expire dates, status.

- [ ] **Step 4: Wire routes and nav**

`App.tsx`:
```tsx
<Route path="/knowledge/dynamic" element={<DynamicKnowledgeListPage />} />
<Route path="/knowledge/dynamic/:id" element={<DynamicKnowledgeDetailPage />} />
```

`AppShell.tsx` NAV_ITEMS add:
```tsx
{ key: "/knowledge/dynamic", label: <Link to="/knowledge/dynamic">动态知识</Link> },
```

Update `getSelectedNavKey` for `/knowledge/dynamic` prefix.

- [ ] **Step 5: Manual smoke test**

```bash
cd frontend && npm run dev
```

Verify: 动态知识 nav → 新建 → 保存 → 列表可见。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/dynamicKnowledge.ts \
  frontend/src/pages/Knowledge/DynamicKnowledgeListPage.tsx \
  frontend/src/pages/Knowledge/DynamicKnowledgeDetailPage.tsx \
  frontend/src/App.tsx \
  frontend/src/layout/AppShell.tsx
git commit -m "feat: add dynamic knowledge management pages"
```

---

## Task 15: 全量验证

- [ ] **Step 1: Run backend tests**

```bash
cd backend && ../.venv/bin/pytest -q
```

Expected: all PASS

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: all PASS

- [ ] **Step 3: Run migration on clean DB (optional sanity)**

```bash
cd backend && ../.venv/bin/alembic upgrade head
```

- [ ] **Step 4: Final commit if any fixups**

```bash
git status
git commit -m "chore: knowledge taxonomy rollout verification fixes"
```

---

## Spec Coverage Self-Review

| Spec 要求 | 对应 Task |
|-----------|-----------|
| `knowledge_taxonomy` 单表四维度 | Task 2–3 |
| 种子数据两级 block_type | Task 2 |
| chunks DROP 旧字段 + 新三字段 | Task 3, 6 |
| TRUNCATE 历史 chunks | Task 3 migration |
| `dynamic_knowledge_records` | Task 3, 9 |
| taxonomy 只读 API | Task 5 |
| chunk API 换字段 + labels + is_expired | Task 7 |
| expired_only 筛选 | Task 7 |
| prefill LLM taxonomy | Task 8 |
| 动态知识 CRUD API | Task 9 |
| 前端 taxonomy hook + 级联 | Task 11–12 |
| 录入/浏览/详情 UI | Task 13 |
| 动态知识页面 | Task 14 |
| 全量测试更新 | Task 10, 15 |

No placeholder steps. Types consistent: `block_type_code`, `application_type_code`, `business_line_codes` used throughout.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-28-knowledge-taxonomy.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
