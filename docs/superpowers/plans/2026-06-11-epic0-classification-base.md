# Epic 0 分类底座 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付多 KB 平台壳层（P0）及 Product Category / Chapter Taxonomy 分类治理（P1–P3），含 API、管理后台、审计与生命周期。

**Architecture:** Monorepo：`backend/` FastAPI + SQLAlchemy + PostgreSQL；`frontend/` React + Ant Design。纵向切片 P0→P1→P2→P3，每片含 API + UI + 测试。共享 `KBContext`、`audit` middleware、`kb_write_guard`。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, psycopg, pytest, httpx | TypeScript, React 18, Ant Design 5, Vite, Playwright

**Design doc:** `docs/superpowers/specs/2026-06-11-epic0-classification-base-design.md`  
**Feature spec:** `specs/001-classification-base/spec.md`

---

## File Map（将创建的主要文件）

| 路径 | 职责 |
|------|------|
| `docker-compose.yml` | PostgreSQL 15 |
| `backend/pyproject.toml` | Python 依赖 |
| `backend/src/main.py` | FastAPI app 入口 |
| `backend/src/db/session.py` | DB engine/session |
| `backend/src/api/envelope.py` | 统一响应 envelope |
| `backend/src/api/deps.py` | DB、operator、kb_write_guard |
| `backend/src/api/middleware/audit.py` | trace_id 上下文 |
| `backend/src/models/*.py` | ORM 实体 |
| `backend/src/services/*.py` | 业务逻辑 |
| `backend/src/api/routes/*.py` | HTTP 路由 |
| `backend/tests/conftest.py` | test client + db fixture |
| `frontend/src/layout/*` | AppShell、KBContext |
| `frontend/src/pages/*` | 各中心页面 |

---

## Phase P0 — KB 平台壳层

### Task 1: 项目脚手架与 Docker

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/pyproject.toml`
- Create: `backend/src/main.py`
- Create: `backend/startup.py`
- Create: `backend/src/db/session.py`

- [ ] **Step 1: 创建 docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: tender
      POSTGRES_PASSWORD: tender
      POSTGRES_DB: tender_knowledge
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

- [ ] **Step 2: 创建 backend/pyproject.toml**

```toml
[project]
name = "tender-knowledge-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.32.0",
  "sqlalchemy>=2.0.36",
  "alembic>=1.14.0",
  "psycopg[binary]>=3.2.0",
  "pydantic>=2.10.0",
  "pydantic-settings>=2.6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.3.0", "pytest-asyncio>=0.24.0", "httpx>=0.28.0"]

[build-system]
requires = ["setuptools>=75.0.0"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: 创建 backend/src/db/session.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://tender:tender@localhost:5432/tender_knowledge",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: 创建 backend/src/main.py 与 startup.py**

```python
# backend/src/main.py
from fastapi import FastAPI

app = FastAPI(title="tender_knowledge", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
```

```python
# backend/startup.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 5: 验证**

```bash
docker compose up -d postgres
cd backend && python -m venv ../.venv && source ../.venv/bin/activate
pip install -e ".[dev]"
python startup.py &
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml backend/
git commit -m "chore: scaffold backend and postgres for epic0"
```

---

### Task 2: API Envelope 与 Audit Middleware

**Files:**
- Create: `backend/src/api/envelope.py`
- Create: `backend/src/api/middleware/audit.py`
- Modify: `backend/src/main.py`
- Test: `backend/tests/unit/test_envelope.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_envelope.py
from src.api.envelope import success, error
import uuid

def test_success_envelope_has_trace_id():
    tid = uuid.uuid4()
    body = success({"id": "1"}, trace_id=tid)
    assert body["data"] == {"id": "1"}
    assert body["trace_id"] == str(tid)

def test_error_envelope():
    tid = uuid.uuid4()
    body = error("CONFLICT", "duplicate", trace_id=tid, details={"field": "alias"})
    assert body["error"]["code"] == "CONFLICT"
    assert body["trace_id"] == str(tid)
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && pytest tests/unit/test_envelope.py -v
```

Expected: FAIL `ModuleNotFoundError`

- [ ] **Step 3: 实现 envelope.py**

```python
# backend/src/api/envelope.py
from __future__ import annotations
import uuid
from typing import Any


def new_trace_id() -> uuid.UUID:
    return uuid.uuid4()


def success(data: Any, trace_id: uuid.UUID | None = None) -> dict:
    tid = trace_id or new_trace_id()
    return {"data": data, "trace_id": str(tid)}


def error(
    code: str,
    message: str,
    *,
    trace_id: uuid.UUID | None = None,
    details: dict | None = None,
) -> dict:
    tid = trace_id or new_trace_id()
    return {
        "error": {"code": code, "message": message, "details": details or {}},
        "trace_id": str(tid),
    }
```

- [ ] **Step 4: 实现 audit context（middleware/audit.py）**

```python
# backend/src/api/middleware/audit.py
from contextvars import ContextVar
import uuid

trace_id_var: ContextVar[uuid.UUID] = ContextVar("trace_id", default=None)
operator_id_var: ContextVar[str] = ContextVar("operator_id", default="system")


def get_trace_id() -> uuid.UUID:
    tid = trace_id_var.get()
    if tid is None:
        tid = uuid.uuid4()
        trace_id_var.set(tid)
    return tid


def set_operator_id(operator_id: str) -> None:
    operator_id_var.set(operator_id or "system")
```

- [ ] **Step 5: 测试通过**

```bash
pytest tests/unit/test_envelope.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/src/api/ backend/tests/unit/test_envelope.py
git commit -m "feat: add API response envelope and audit context"
```

---

### Task 3: KnowledgeBase 模型与迁移

**Files:**
- Create: `backend/src/models/knowledge_base.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_knowledge_base.py`
- Test: `backend/tests/integration/test_kb_model.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/integration/test_kb_model.py
from sqlalchemy import select
from src.db.session import SessionLocal, Base, engine
from src.models.knowledge_base import KnowledgeBase, KBStatus

def test_create_knowledge_base():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        kb = KnowledgeBase(name="标书知识库-demo", status=KBStatus.active)
        db.add(kb)
        db.commit()
        db.refresh(kb)
        found = db.scalar(select(KnowledgeBase).where(KnowledgeBase.name == "标书知识库-demo"))
        assert found is not None
        assert found.status == KBStatus.active
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
```

- [ ] **Step 2: 实现模型**

```python
# backend/src/models/knowledge_base.py
import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from src.db.session import Base


class KBStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[KBStatus] = mapped_column(Enum(KBStatus), nullable=False, default=KBStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 3: 运行测试通过**

```bash
pytest tests/integration/test_kb_model.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/models/knowledge_base.py backend/tests/integration/test_kb_model.py
git commit -m "feat: add KnowledgeBase model"
```

---

### Task 4: KB REST API（CRUD + deactivate）

**Files:**
- Create: `backend/src/schemas/knowledge_base.py`
- Create: `backend/src/services/kb_service.py`
- Create: `backend/src/api/routes/knowledge_bases.py`
- Create: `backend/src/api/deps.py`
- Modify: `backend/src/main.py`
- Test: `backend/tests/contract/test_knowledge_bases_api.py`

- [ ] **Step 1: 写失败 contract 测试**

```python
# backend/tests/contract/test_knowledge_bases_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.db.session import Base, engine

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_create_and_list_kb():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v1/kbs",
            json={"name": "KB-A"},
            headers={"X-Operator-Id": "admin"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["name"] == "KB-A"
        assert "trace_id" in body

        r2 = await client.get("/api/v1/kbs?status=active")
        assert r2.status_code == 200
        assert len(r2.json()["data"]["items"]) == 1
```

- [ ] **Step 2: 实现 kb_service.py**

```python
# backend/src/services/kb_service.py
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models.knowledge_base import KnowledgeBase, KBStatus


def create_kb(db: Session, name: str) -> KnowledgeBase:
    kb = KnowledgeBase(name=name, status=KBStatus.active)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def list_kbs(db: Session, status: KBStatus | None = KBStatus.active) -> list[KnowledgeBase]:
    stmt = select(KnowledgeBase)
    if status is not None:
        stmt = stmt.where(KnowledgeBase.status == status)
    return list(db.scalars(stmt.order_by(KnowledgeBase.created_at)))


def get_kb(db: Session, kb_id) -> KnowledgeBase | None:
    return db.get(KnowledgeBase, kb_id)


def update_kb_name(db: Session, kb: KnowledgeBase, name: str) -> KnowledgeBase:
    kb.name = name
    db.commit()
    db.refresh(kb)
    return kb


def deactivate_kb(db: Session, kb: KnowledgeBase) -> KnowledgeBase:
    kb.status = KBStatus.inactive
    db.commit()
    db.refresh(kb)
    return kb
```

- [ ] **Step 3: 实现 routes + deps + 注册 router**

```python
# backend/src/api/deps.py
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.models.knowledge_base import KnowledgeBase, KBStatus
from src.api.middleware.audit import set_operator_id


def get_operator_id(x_operator_id: str = Header(default="system", alias="X-Operator-Id")) -> str:
    set_operator_id(x_operator_id)
    return x_operator_id


def get_kb_or_404(kb_id, db: Session = Depends(get_db)) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="KB not found")
    return kb


def kb_write_guard(kb: KnowledgeBase = Depends(get_kb_or_404)) -> KnowledgeBase:
    if kb.status == KBStatus.inactive:
        raise HTTPException(status_code=403, detail={"code": "KB_READ_ONLY", "message": "KB is read-only"})
    return kb
```

```python
# backend/src/api/routes/knowledge_bases.py
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.api.envelope import success
from src.api.middleware.audit import get_trace_id
from src.api.deps import get_db, get_operator_id, get_kb_or_404
from src.services import kb_service

router = APIRouter(prefix="/api/v1/kbs", tags=["knowledge-bases"])


class CreateKBRequest(BaseModel):
    name: str
    clone_from_kb_id: UUID | None = None


class PatchKBRequest(BaseModel):
    name: str


@router.post("")
def create_kb(body: CreateKBRequest, db: Session = Depends(get_db), _: str = Depends(get_operator_id)):
    kb = kb_service.create_kb(db, body.name)
    # clone_from_kb_id handled in Task 5
    return success({"kb_id": str(kb.kb_id), "name": kb.name, "status": kb.status.value}, trace_id=get_trace_id())


@router.get("")
def list_kbs(status: str = "active", db: Session = Depends(get_db)):
    from src.models.knowledge_base import KBStatus
    st = KBStatus(status) if status else None
    items = kb_service.list_kbs(db, st)
    return success({"items": [{"kb_id": str(k.kb_id), "name": k.name, "status": k.status.value} for k in items]}, trace_id=get_trace_id())


@router.get("/{kb_id}")
def get_kb_detail(kb=Depends(get_kb_or_404)):
    return success({"kb_id": str(kb.kb_id), "name": kb.name, "status": kb.status.value}, trace_id=get_trace_id())


@router.patch("/{kb_id}")
def patch_kb(body: PatchKBRequest, kb: KnowledgeBase = Depends(get_kb_or_404), db: Session = Depends(get_db)):
    kb = kb_service.update_kb_name(db, kb, body.name)
    return success({"kb_id": str(kb.kb_id), "name": kb.name}, trace_id=get_trace_id())


@router.post("/{kb_id}/deactivate")
def deactivate_kb(kb: KnowledgeBase = Depends(get_kb_or_404), db: Session = Depends(get_db)):
    kb = kb_service.deactivate_kb(db, kb)
    return success({"kb_id": str(kb.kb_id), "status": kb.status.value}, trace_id=get_trace_id())
```

在 `main.py` 中：`from src.api.routes.knowledge_bases import router as kb_router` 并 `app.include_router(kb_router)`。

- [ ] **Step 4: 测试通过**

```bash
pytest tests/contract/test_knowledge_bases_api.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/api backend/src/services/kb_service.py backend/tests/contract/test_knowledge_bases_api.py backend/src/main.py
git commit -m "feat: add knowledge base REST API"
```

---

### Task 5: KB Clone Service

**Files:**
- Create: `backend/src/models/kb_clone_log.py`
- Create: `backend/src/services/kb_clone_service.py`
- Modify: `backend/src/api/routes/knowledge_bases.py`
- Test: `backend/tests/integration/test_kb_clone.py`

- [ ] **Step 1: 写失败测试**（空 KB clone：仅验证 kb_clone_log；含分类树的 clone 集成测试在 Task 7 后追加）

```python
# backend/tests/integration/test_kb_clone.py
from sqlalchemy import select
from src.db.session import SessionLocal, Base, engine
from src.models.knowledge_base import KnowledgeBase
from src.models.kb_clone_log import KBCloneLog
from src.services import kb_service
from src.services.kb_clone_service import clone_kb


def test_clone_empty_kb_writes_log():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        source = kb_service.create_kb(db, "source-kb")
        target = kb_service.create_kb(db, "target-kb")
        clone_kb(db, source.kb_id, target.kb_id, operator_id="admin", trace_id="trace-1")
        log = db.scalar(
            select(KBCloneLog).where(KBCloneLog.target_kb_id == target.kb_id)
        )
        assert log is not None
        assert log.source_kb_id == source.kb_id
        assert source.kb_id != target.kb_id
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
```

- [ ] **Step 2: 实现 kb_clone_log 模型与 kb_clone_service.py**

```python
# backend/src/services/kb_clone_service.py
from uuid import UUID
from sqlalchemy.orm import Session
from src.models.kb_clone_log import KBCloneLog

MAX_NODES = 2000


def clone_kb(db: Session, source_kb_id: UUID, target_kb_id: UUID, operator_id: str, trace_id: str) -> None:
    # 当 product/chapter 表存在后，在此按 depth 复制；Epic 0 先写 log 并 commit
    log = KBCloneLog(
        target_kb_id=target_kb_id,
        source_kb_id=source_kb_id,
        operator_id=operator_id,
        trace_id=trace_id,
    )
    db.add(log)
    db.commit()
```

Task 7 完成后扩展 `clone_kb`：读取源分类树 → `id_map` → 批量 insert（节点数 > MAX_NODES 抛 ValueError）。

- [ ] **Step 3: 在 create_kb route 中若 `clone_from_kb_id` 则调用 clone_kb**

- [ ] **Step 4: pytest 通过 + commit**

```bash
git commit -m "feat: add KB deep clone for classification trees"
```

---

### Task 6: 前端 P0 — KB 列表与切换器

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/main.tsx`
- Create: `frontend/src/layout/KBContext.tsx`
- Create: `frontend/src/layout/AppShell.tsx`
- Create: `frontend/src/pages/KnowledgeBaseList/index.tsx`
- Create: `frontend/src/services/apiClient.ts`, `frontend/src/services/kbApi.ts`

- [ ] **Step 1: Vite + React + Ant Design 初始化**

```bash
cd frontend && npm create vite@latest . -- --template react-ts
npm install antd react-router-dom
```

- [ ] **Step 2: 实现 KBContext**

```tsx
// frontend/src/layout/KBContext.tsx
import React, { createContext, useContext, useEffect, useState } from "react";

type KBContextValue = {
  kbId: string | null;
  setKbId: (id: string | null) => void;
  readOnly: boolean;
  setReadOnly: (v: boolean) => void;
};

const KBContext = createContext<KBContextValue | null>(null);
const STORAGE_KEY = "tender_kb_id";

export function KBProvider({ children }: { children: React.ReactNode }) {
  const [kbId, setKbIdState] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));
  const [readOnly, setReadOnly] = useState(false);

  const setKbId = (id: string | null) => {
    setKbIdState(id);
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <KBContext.Provider value={{ kbId, setKbId, readOnly, setReadOnly }}>
      {children}
    </KBContext.Provider>
  );
}

export function useKB() {
  const ctx = useContext(KBContext);
  if (!ctx) throw new Error("useKB must be used within KBProvider");
  return ctx;
}
```

- [ ] **Step 3: KnowledgeBaseList 页 — 表格 + 创建 Modal（含 clone 下拉选源 KB）**

- [ ] **Step 4: AppShell 顶栏 KBSwitcher（Select 组件，仅 active KB）**

- [ ] **Step 5: 手动验证** — 创建 KB、切换、停用后 readOnly banner

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: add KB list page and global KB switcher"
```

**P0 Checkpoint:** quickstart VS-0 — 两 KB（空+复制）、切换、inactive 只读。

---

## Phase P1 — 产品分类中心

### Task 7: Product Category 模型与 category_tree 服务

**Files:**
- Create: `backend/src/models/product_category.py`
- Create: `backend/src/services/category_tree.py`
- Create: `backend/src/services/alias_registry.py`
- Create: `backend/alembic/versions/002_product_category.py`
- Test: `backend/tests/unit/test_category_tree.py`

- [ ] **Step 1: 写 test_category_tree 失败测试**

```python
# backend/tests/unit/test_category_tree.py
from src.services.category_tree import build_path, assert_no_cycle

def test_build_path_root():
    assert build_path(None, "uuid-1") == "/uuid-1/"

def test_build_path_child():
    assert build_path("/parent/", "child") == "/parent/child/"
```

- [ ] **Step 2: 实现 category_tree.py**

```python
def build_path(parent_path: str | None, node_id: str) -> str:
    if not parent_path:
        return f"/{node_id}/"
    return f"{parent_path.rstrip('/')}/{node_id}/"

def assert_no_cycle(parent_path: str | None, node_id: str) -> None:
    if parent_path and f"/{node_id}/" in parent_path:
        raise ValueError("CYCLE_DETECTED")
```

- [ ] **Step 3: ProductCategory + ProductCategoryAlias ORM（见 data-model.md）**

- [ ] **Step 4: alias_registry.normalize(name) -> str；check_unique(db, kb_id, names)**

- [ ] **Step 5: pytest 通过 + migration + commit**

---

### Task 8: Product Category API

**Files:**
- Create: `backend/src/services/product_category_service.py`
- Create: `backend/src/api/routes/product_categories.py`
- Test: `backend/tests/contract/test_product_categories_api.py`

- [ ] **Step 1: contract 测试 — POST 创建根+子、GET tree、PUT aliases、GET search**

```python
@pytest.mark.asyncio
async def test_create_three_level_tree():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        kb = await client.post("/api/v1/kbs", json={"name": "KB"}, headers={"X-Operator-Id": "admin"})
        kb_id = kb.json()["data"]["kb_id"]
        root = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={"category_name": "福利产品", "category_code": "welfare", "aliases": []},
            headers={"X-Operator-Id": "admin"},
        )
        root_id = root.json()["data"]["category_id"]
        child = await client.post(
            f"/api/v1/kbs/{kb_id}/product-categories",
            json={"parent_id": root_id, "category_name": "餐补", "category_code": "meal", "aliases": ["员工餐补"]},
            headers={"X-Operator-Id": "admin"},
        )
        assert child.status_code == 200
        tree = await client.get(f"/api/v1/kbs/{kb_id}/product-categories/tree")
        nodes = tree.json()["data"]["nodes"]
        assert len(nodes) == 1
        assert len(nodes[0]["children"]) == 1
```

- [ ] **Step 2: 实现 service + routes（依赖 kb_write_guard）**

路由对照 `specs/001-classification-base/contracts/product-category-api.md`。

- [ ] **Step 3: 别名冲突返回 409 CONFLICT**

- [ ] **Step 4: pytest 通过 + commit**

```bash
git commit -m "feat: add product category API"
```

---

### Task 9: 产品分类中心 UI

**Files:**
- Create: `frontend/src/components/CategoryTreePanel.tsx`
- Create: `frontend/src/components/CategoryDetailPanel.tsx`
- Create: `frontend/src/pages/ProductCategoryCenter/index.tsx`
- Create: `frontend/src/services/productCategoryApi.ts`

- [ ] **Step 1: 左 Tree（Ant Design Tree）+ 右 Form（名称、编码、描述、别名 Tag 输入）**

- [ ] **Step 2: readOnly 时禁用保存**

- [ ] **Step 3: Playwright 冒烟 `frontend/tests/product-category.spec.ts`**

```typescript
test("create root category", async ({ page }) => {
  await page.goto("/product-categories");
  await page.getByRole("button", { name: "新建分类" }).click();
  await page.getByLabel("名称").fill("福利产品");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText("福利产品")).toBeVisible();
});
```

- [ ] **Step 4: Commit**

**P1 Checkpoint:** SC-001 — 5 分钟内三级分类+别名（manual quickstart VS-1）。

---

## Phase P2 — 章节目录中心

### Task 10: Chapter Taxonomy 模型与 API

**Files:**
- Create: `backend/src/models/chapter_taxonomy.py`
- Create: `backend/src/services/chapter_taxonomy_service.py`
- Create: `backend/src/api/routes/chapter_taxonomies.py`
- Test: `backend/tests/contract/test_chapter_taxonomies_api.py`

- [ ] **Step 1: ORM — ChapterTaxonomy, Synonym, Binding（binding.source 默认 manual）**

- [ ] **Step 2: contract 测试 — 同义名、M:N 绑定、按 product_category_id 筛选**

- [ ] **Step 3: 实现 routes（对照 chapter-taxonomy-api.md）**

- [ ] **Step 4: Commit**

---

### Task 11: 章节目录中心 UI

**Files:**
- Create: `frontend/src/pages/ChapterTaxonomyCenter/index.tsx`
- Create: `frontend/src/services/chapterTaxonomyApi.ts`

- [ ] **Step 1: 复用 CategoryTreePanel/DetailPanel，字段改为 standard_name + synonyms**

- [ ] **Step 2: 产品分类多选 Select（options 来自 product category active tree）**

- [ ] **Step 3: Commit**

**P2 Checkpoint:** SC-002 quickstart VS-2。

---

## Phase P3 — 分类生命周期

### Task 12: Classification Reference + Impact Analysis

**Files:**
- Create: `backend/src/models/classification_reference.py`
- Create: `backend/src/services/impact_analysis.py`
- Create: `backend/scripts/seed_classification_references.py`
- Test: `backend/tests/integration/test_impact_analysis.py`

- [ ] **Step 1: reference 模型 + migration**

- [ ] **Step 2: impact_analysis.get_report(db, kb_id, classification_type, classification_id)**

```python
# backend/src/services/impact_analysis.py
from sqlalchemy import func, select
from src.models.classification_reference import ClassificationReference

def get_report(db, kb_id, classification_type, classification_id) -> dict:
    rows = db.execute(
        select(
            ClassificationReference.object_type,
            func.count().label("count"),
        )
        .where(
            ClassificationReference.kb_id == kb_id,
            ClassificationReference.classification_type == classification_type,
            ClassificationReference.classification_id == classification_id,
        )
        .group_by(ClassificationReference.object_type)
    ).all()
    by_type = {row.object_type: row.count for row in rows}
    return {
        "classification_type": classification_type,
        "classification_id": str(classification_id),
        "total_count": sum(by_type.values()),
        "by_object_type": by_type,
    }
```

- [ ] **Step 3: seed 脚本插入 5 条 ku + 3 条 candidate 引用

- [ ] **Step 4: GET .../impact contract 测试 < 3s

- [ ] **Step 5: Commit**

---

### Task 13: Merge Service + Lifecycle Routes

**Files:**
- Create: `backend/src/services/merge_service.py`
- Create: `backend/src/models/audit_log.py`
- Modify: `backend/src/api/routes/product_categories.py`
- Modify: `backend/src/api/routes/chapter_taxonomies.py`
- Test: `backend/tests/integration/test_merge.py`

- [ ] **Step 1: 写失败测试 — 有子节点合并 → 409 HAS_CHILDREN**

```python
# backend/src/services/merge_service.py
class MergeError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

def merge_product_category(db, source, target):
    if source.has_active_children(db):
        raise MergeError("HAS_CHILDREN", "Source category has child nodes")
    if is_ancestor(source, target) or is_ancestor(target, source):
        raise MergeError("ANCESTOR_RELATION", "Cannot merge ancestor and descendant")
    migrate_references(db, source.category_id, target.category_id)
    source.status = "merged"
    source.merged_into_id = target.category_id
    db.commit()

# backend/tests/integration/test_merge.py
def test_merge_rejects_when_source_has_children(db, parent, child, other):
    with pytest.raises(MergeError) as exc:
        merge_product_category(db, source=parent, target=other)
    assert exc.value.code == "HAS_CHILDREN"
```

- [ ] **Step 2: merge_service 实现 D7/D8 + reference 迁移 + dedupe**

- [ ] **Step 3: deactivate 父节点有 active 子 → HAS_ACTIVE_CHILDREN**

- [ ] **Step 4: 每次写操作写 classification_audit_log**

- [ ] **Step 5: Commit**

---

### Task 14: 生命周期 UI（影响分析 + 合并向导）

**Files:**
- Create: `frontend/src/components/ImpactAnalysisModal.tsx`
- Create: `frontend/src/components/MergeWizard.tsx`
- Modify: `frontend/src/pages/ProductCategoryCenter/index.tsx`
- Modify: `frontend/src/pages/ChapterTaxonomyCenter/index.tsx`

- [ ] **Step 1: ImpactAnalysisModal 展示 by_object_type 表格**

- [ ] **Step 2: MergeWizard — 选目标分类 → 展示 impact → 确认**

- [ ] **Step 3: 停用/归档按钮 + 确认**

- [ ] **Step 4: Commit**

**P3 Checkpoint:** quickstart VS-3、SC-003、SC-005。

---

### Task 15: 文档同步与全量验收

**Files:**
- Modify: `specs/001-classification-base/quickstart.md`
- Create: `specs/001-classification-base/contracts/knowledge-base-api.md`
- Modify: `specs/001-classification-base/plan.md`（P0 切片）
- Modify: `specs/001-classification-base/data-model.md`（kb_clone_log）

- [ ] **Step 1: 更新 quickstart 增加 P0 VS 场景**

- [ ] **Step 2: 运行全量后端测试**

```bash
cd backend && pytest -v
```

- [ ] **Step 3: 按 quickstart.md 手工走通 VS-1 至 VS-5**

- [ ] **Step 4: Commit**

```bash
git commit -m "docs: sync epic0 quickstart and contracts after implementation"
```

---

## Spec Coverage Self-Review

| Spec 要求 | Task |
|-----------|------|
| FR-001–003 Product Category | Task 7–9 |
| FR-004–005 Chapter Taxonomy | Task 10–11 |
| FR-006–008 生命周期 | Task 12–14 |
| FR-009 管理能力 API | Task 4, 8, 10 |
| FR-010 审计 | Task 2, 13 |
| FR-011 manual>suggested 预留 | Task 10 binding.source |
| FR-012 不在范围 | 未建路由 |
| P0 多 KB（设计 doc） | Task 4–6 |
| SC-001–006 | P1–P3 checkpoints |

无 TBD/TODO 占位；类型命名 `kb_write_guard`、`merge_product_category` 全文一致。

---

## 执行顺序依赖图

```text
Task 1 → 2 → 3 → 4 → 5 → 6 (P0)
              ↓
         7 → 8 → 9 (P1)
              ↓
            10 → 11 (P2)
              ↓
            12 → 13 → 14 (P3)
              ↓
            15 (docs)
```

Task 5 依赖 Task 7 的分类模型（可先空 clone，Task 7 后补集成测试）。
