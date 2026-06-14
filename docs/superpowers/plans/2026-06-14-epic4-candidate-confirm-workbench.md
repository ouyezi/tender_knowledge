# Epic 4 候选知识确认工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付候选知识治理闭环：列表筛选 → Drawer 轻编辑 → 全屏 7 类型发布 → 合并/拆分 → 批量确认 → 审计日志；未确认候选与正式 KU 检索隔离。

**Architecture:** 混合 UX（`/candidates` + `/candidates/confirm/:id`）。`CandidateAdapter` 统一 `doc_`/`tpl_` 双源；`candidate_publish_service` 编排 7 publisher；新建 `knowledge_units`/`wikis`/`manual_assets`/`candidate_confirm_audit_logs`。纵向切片 P0→P4，MVP 停点在 P1 结束（单条全类型发布）。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL/SQLite test | React 18, Ant Design 5, Vite, ProComponents | pytest, httpx, Vitest

**Design doc:** `docs/superpowers/specs/2026-06-14-epic4-candidate-confirm-workbench-design.md`  
**Feature spec:** `specs/006-candidate-confirm-workbench/spec.md`  
**Spec Kit tasks:** `specs/006-candidate-confirm-workbench/tasks.md` (T001–T063)  
**Data model:** `specs/006-candidate-confirm-workbench/data-model.md`  
**Contracts:** `specs/006-candidate-confirm-workbench/contracts/`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/src/models/candidate_knowledge.py` | 扩展 confirmed/lineage/publish 字段 + enum |
| `backend/src/models/candidate_knowledge_stub.py` | stub 通道同名字段 |
| `backend/src/models/knowledge_unit.py` | 正式 KU ORM |
| `backend/src/models/wiki.py` | 正式 Wiki ORM |
| `backend/src/models/manual_asset.py` | 正式 Manual Asset ORM |
| `backend/src/models/candidate_confirm_audit_log.py` | 确认审计 ORM |
| `backend/src/services/candidate_adapter.py` | `doc_`/`tpl_` 解析 + `CandidateView` |
| `backend/src/services/candidate_audit_service.py` | 审计写入 |
| `backend/src/services/candidate_edit_service.py` | PATCH 编辑 |
| `backend/src/services/candidate_publish_validator.py` | 发布前校验 |
| `backend/src/services/candidate_publish_service.py` | 发布编排器 |
| `backend/src/services/publishers/*.py` | 7 类型 publisher + ignore |
| `backend/src/services/candidate_merge_service.py` | merge/split |
| `backend/src/api/routes/candidates.py` | 扩展 list/PATCH/confirm/merge/split |
| `backend/src/api/routes/candidate_batch.py` | batch confirm/reject |
| `backend/src/api/routes/candidate_audit_logs.py` | audit GET |
| `backend/src/api/routes/knowledge_units.py` | KU 只读 list/get |
| `backend/src/api/routes/wikis.py` | Wiki 只读 |
| `backend/src/api/routes/manual_assets.py` | Manual Asset 只读 |
| `backend/tests/contract/test_candidates_list.py` | 已有 seed 辅助函数（复用） |
| `frontend/src/pages/CandidateCenter/index.tsx` | ProTable + 多选 + Drawer |
| `frontend/src/pages/CandidateCenter/CandidateDetailDrawer.tsx` | 轻编辑 |
| `frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx` | 全屏两栏 Tab |
| `frontend/src/pages/CandidateCenter/BatchConfirmModal.tsx` | 批量策略 Modal |
| `frontend/src/pages/CandidateCenter/BatchResultDrawer.tsx` | 批量结果 |
| `frontend/src/pages/CandidateCenter/CandidateMergeModal.tsx` | 合并 |
| `frontend/src/pages/CandidateCenter/CandidateSplitModal.tsx` | 拆分 |
| `frontend/src/pages/CandidateCenter/CandidateAuditPanel.tsx` | 审计 Tab |
| `frontend/src/services/candidates.ts` | API client 扩展 |
| `frontend/src/services/candidateAudit.ts` | 审计 client |

---

## Phase P0 — 基建（阻塞，对应 T001–T015）

### Task P0-1: Epic 4 ORM 与 conftest 注册

**Files:**
- Modify: `backend/src/models/candidate_knowledge.py`
- Modify: `backend/src/models/candidate_knowledge_stub.py`
- Create: `backend/src/models/knowledge_unit.py`
- Create: `backend/src/models/wiki.py`
- Create: `backend/src/models/manual_asset.py`
- Create: `backend/src/models/candidate_confirm_audit_log.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/db/init_db.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_epic4_models.py`

- [ ] **Step 1: 写集成测试**

```python
# backend/tests/integration/test_epic4_models.py
from uuid import uuid4

from src.models.candidate_confirm_audit_log import (
    CandidateConfirmAuditAction,
    CandidateConfirmAuditLog,
)
from src.models.knowledge_unit import KnowledgeUnit, KnowledgeUnitStatus


def test_create_knowledge_unit_with_candidate_source(db_session):
    kb_id = uuid4()
    import_id = uuid4()
    candidate_id = uuid4()
    ku = KnowledgeUnit(
        kb_id=kb_id,
        title="云平台架构设计",
        content="正文",
        knowledge_type="solution",
        product_category_ids=[],
        import_id=import_id,
        candidate_id=candidate_id,
        published_by="admin",
        status=KnowledgeUnitStatus.published,
    )
    db_session.add(ku)
    db_session.add(
        CandidateConfirmAuditLog(
            kb_id=kb_id,
            candidate_id=f"doc_{candidate_id}",
            action=CandidateConfirmAuditAction.publish,
            operator_id="admin",
            trace_id=uuid4(),
            detail={"confirm_as": "ku"},
        )
    )
    db_session.commit()
    assert ku.ku_id is not None
```

- [ ] **Step 2: 扩展 `CandidateKnowledgeType`**

```python
# backend/src/models/candidate_knowledge.py
class CandidateKnowledgeType(str, enum.Enum):
    ku = "ku"
    wiki = "wiki"
    template_chapter = "template_chapter"
    manual_asset = "manual_asset"
    chapter_pattern = "chapter_pattern"
    product_category = "product_category"
    ignore = "ignore"
```

在 `CandidateKnowledge` 增加字段（见 `data-model.md`）：`confirmed_object_type`, `confirmed_object_id`, `searchable`, `usage_hint`, `review_comment`, `merged_into_id`, `split_from_id`, `lineage`, `last_publish_error`, `publish_attempt_count`, `updated_by`。

- [ ] **Step 3: 实现 `KnowledgeUnit` ORM**

```python
# backend/src/models/knowledge_unit.py
class KnowledgeUnitStatus(str, enum.Enum):
    published = "published"
    deprecated = "deprecated"


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"
    ku_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    product_category_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    chapter_taxonomy_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    import_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("file_imports.import_id"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_node_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    searchable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[KnowledgeUnitStatus] = mapped_column(Enum(KnowledgeUnitStatus), nullable=False, default=KnowledgeUnitStatus.published)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_by: Mapped[str] = mapped_column(String(128), nullable=False)
    # ... created_at / updated_at 同项目惯例
```

按 `data-model.md` 同样实现 `Wiki`、`ManualAsset`、`CandidateConfirmAuditLog`（action enum: edit, publish, publish_failed, ignore, merge, split, batch_confirm, batch_reject）。

- [ ] **Step 4: 更新 `init_db.py` 与 `conftest.py` imports**

```python
# backend/tests/conftest.py models import 增加:
    candidate_confirm_audit_log,
    knowledge_unit,
    manual_asset,
    wiki,
```

- [ ] **Step 5: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_epic4_models.py -v
```

Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add backend/src/models/ backend/src/db/init_db.py backend/tests/
git commit -m "feat(epic4): add confirm workbench ORM models"
```

---

### Task P0-2: CandidateAdapter 单元测试与实现

**Files:**
- Create: `backend/src/services/candidate_adapter.py`
- Create: `backend/tests/unit/test_candidate_adapter.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_candidate_adapter.py
import pytest
from uuid import uuid4

from src.models.candidate_knowledge import CandidateKnowledgeStatus
from src.services.candidate_adapter import (
    CandidateNotEditableError,
    parse_candidate_id,
    format_candidate_id,
)


def test_parse_candidate_id_doc_prefix():
    raw = uuid4()
    channel, cid = parse_candidate_id(f"doc_{raw}")
    assert channel == "document"
    assert cid == raw


def test_parse_candidate_id_tpl_prefix():
    raw = uuid4()
    channel, cid = parse_candidate_id(f"tpl_{raw}")
    assert channel == "template"
    assert cid == raw


def test_format_candidate_id_roundtrip():
    raw = uuid4()
    assert parse_candidate_id(format_candidate_id("document", raw)) == ("document", raw)


def test_assert_editable_rejects_published():
    from src.services.candidate_adapter import assert_editable

    with pytest.raises(CandidateNotEditableError):
        assert_editable(CandidateKnowledgeStatus.published)
```

- [ ] **Step 2: 实现 adapter**

```python
# backend/src/services/candidate_adapter.py
from dataclasses import dataclass
from uuid import UUID

from src.models.candidate_knowledge import CandidateKnowledgeStatus


class CandidateNotEditableError(Exception):
    pass


@dataclass
class CandidateView:
    candidate_id: str
    channel: str
    raw_id: UUID
    title: str
    content: str | None
    summary: str | None
    status: str
    candidate_type: str
    # ... suggested fields, source_trace


def parse_candidate_id(candidate_id: str) -> tuple[str, UUID]:
    if candidate_id.startswith("doc_"):
        return "document", UUID(candidate_id.removeprefix("doc_"))
    if candidate_id.startswith("tpl_"):
        return "template", UUID(candidate_id.removeprefix("tpl_"))
    raise ValueError("invalid candidate_id")


def format_candidate_id(channel: str, raw_id: UUID) -> str:
    prefix = "doc_" if channel == "document" else "tpl_"
    return f"{prefix}{raw_id}"


def assert_editable(status: CandidateKnowledgeStatus) -> None:
    if status != CandidateKnowledgeStatus.pending:
        raise CandidateNotEditableError(status.value)
```

补充 `load_candidate(db, kb_id, candidate_id) -> CandidateView`：document 查 `CandidateKnowledge`；template 查 `CandidateKnowledgeStub`（status=`pending_confirm` 映射为 pending）。

- [ ] **Step 3: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_candidate_adapter.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/services/candidate_adapter.py backend/tests/unit/test_candidate_adapter.py
git commit -m "feat(epic4): add candidate adapter for doc/tpl IDs"
```

---

### Task P0-3: 审计 helper + 写 API 路由壳

**Files:**
- Create: `backend/src/services/candidate_audit_service.py`
- Create: `backend/src/api/routes/candidate_batch.py`
- Create: `backend/src/api/routes/candidate_audit_logs.py`
- Create: `backend/src/api/routes/knowledge_units.py`
- Create: `backend/src/api/routes/wikis.py`
- Create: `backend/src/api/routes/manual_assets.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/contract/test_epic4_route_shells.py`

- [ ] **Step 1: 契约测试（空列表）**

```python
# backend/tests/contract/test_epic4_route_shells.py
def test_list_knowledge_units_empty(client, seeded_kb):
    r = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-units",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []


def test_list_candidate_audit_logs_empty(client, seeded_kb):
    r = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidate-audit-logs",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []
```

- [ ] **Step 2: 实现 audit helper**

```python
# backend/src/services/candidate_audit_service.py
def write_audit(
    db,
    *,
    kb_id: UUID,
    candidate_id: str,
    action: CandidateConfirmAuditAction,
    operator_id: str,
    trace_id: UUID,
    detail: dict | None = None,
    batch_id: UUID | None = None,
) -> CandidateConfirmAuditLog:
    row = CandidateConfirmAuditLog(
        kb_id=kb_id,
        candidate_id=candidate_id,
        batch_id=batch_id,
        action=action,
        operator_id=operator_id,
        trace_id=trace_id,
        detail=detail or {},
    )
    db.add(row)
    return row
```

- [ ] **Step 3: 注册 routers**

```python
# backend/src/main.py 增加:
from src.api.routes.candidate_batch import router as candidate_batch_router
from src.api.routes.candidate_audit_logs import router as candidate_audit_logs_router
from src.api.routes.knowledge_units import router as knowledge_units_router
from src.api.routes.wikis import router as wikis_router
from src.api.routes.manual_assets import router as manual_assets_router

app.include_router(knowledge_units_router)
app.include_router(wikis_router)
app.include_router(manual_assets_router)
app.include_router(candidate_batch_router)
app.include_router(candidate_audit_logs_router)
```

写操作路由使用 `Depends(kb_write_guard)`；GET 使用 `get_kb_or_404`。

- [ ] **Step 4: pytest PASS + commit**

```bash
cd backend && ../.venv/bin/pytest tests/contract/test_epic4_route_shells.py -v
git add backend/src/main.py backend/src/api/routes/ backend/src/services/candidate_audit_service.py backend/tests/contract/test_epic4_route_shells.py
git commit -m "feat(epic4): add confirm workbench API route shells"
```

---

### Task P0-4: 前端路由壳

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx`
- Create: `frontend/src/pages/CandidateCenter/CandidateAuditPanel.tsx`

- [ ] **Step 1: 路由**

```tsx
// frontend/src/App.tsx
import CandidateConfirmPage from "./pages/CandidateCenter/CandidateConfirmPage";
import CandidateAuditPanel from "./pages/CandidateCenter/CandidateAuditPanel";

<Route path="/candidates/confirm/:candidateId" element={<CandidateConfirmPage />} />
<Route path="/candidates/audit" element={<CandidateAuditPanel />} />
```

- [ ] **Step 2: 空壳页**

```tsx
// CandidateConfirmPage.tsx — 占位 Alert「确认页开发中」+ useParams candidateId
// CandidateAuditPanel.tsx — 占位 Empty
```

- [ ] **Step 3: 手动验证** `npm run dev`，访问 `/candidates/confirm/doc_test` 不 404

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages/CandidateCenter/
git commit -m "feat(epic4): add confirm page and audit route shells"
```

**P0 Checkpoint:** ORM 集成测 + adapter 单测 + 空 API 200 + 前端路由可达

---

## Phase P1 — 单条闭环（US1–US3，对应 T016–T044）

### Task P1-1: 列表筛选 API（US1）

**Files:**
- Modify: `backend/src/api/routes/candidates.py`
- Create: `backend/tests/contract/test_candidate_list_filters.py`

- [ ] **Step 1: 写失败测试**（复用 `test_candidates_list._seed_document_candidate`）

```python
def test_list_candidates_filter_by_chapter_taxonomy(client, db_session, seeded_kb, seeded_taxonomy):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    candidate.suggested_chapter_taxonomy_id = seeded_taxonomy.taxonomy_id
    db_session.commit()
    other = uuid4()
    r = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates",
        params={"chapter_taxonomy_id": str(seeded_taxonomy.taxonomy_id)},
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    ids = {item["candidate_id"] for item in r.json()["data"]["items"]}
    assert f"doc_{candidate.candidate_id}" in ids
```

- [ ] **Step 2: 在 `list_candidates` 增加 query 参数过滤**

对 document 通道：`chapter_taxonomy_id` 匹配 `suggested_chapter_taxonomy_id`；`product_category_id` 用 JSON 包含；`confidence_min` 过滤 `confidence_score`。

- [ ] **Step 3: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/contract/test_candidate_list_filters.py -v
```

- [ ] **Step 4: Commit**

---

### Task P1-2: 检索隔离负向测试（US1）

**Files:**
- Create: `backend/tests/contract/test_candidate_retrieval_isolation.py`
- Modify: `backend/src/api/routes/knowledge_units.py`

- [ ] **Step 1: 测试 pending 候选 ID 不在 KU 列表**

```python
def test_pending_candidate_not_in_knowledge_units(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    r = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/knowledge-units",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    candidate_ids = {item.get("candidate_id") for item in r.json()["data"]["items"]}
    assert str(candidate.candidate_id) not in candidate_ids
```

- [ ] **Step 2: 确保 KU list 只查 `knowledge_units` 表**（初始为空即 PASS）

- [ ] **Step 3: Commit**

---

### Task P1-3: ProTable 列表 UI（US1）

**Files:**
- Modify: `frontend/src/pages/CandidateCenter/index.tsx`
- Modify: `frontend/src/services/candidates.ts`

- [ ] **Step 1: 扩展 `listCandidates` params**（chapter_taxonomy_id, product_category_id, status, source_channel）

- [ ] **Step 2: ProTable + 筛选 Form + 行操作「发布」→ `navigate(/candidates/confirm/${id})`**

- [ ] **Step 3: 手动验证筛选与跳转**

- [ ] **Step 4: Commit**

---

### Task P1-4: PATCH 编辑（US2）

**Files:**
- Create: `backend/tests/contract/test_candidate_edit.py`
- Create: `backend/src/services/candidate_edit_service.py`
- Modify: `backend/src/api/routes/candidates.py`
- Create: `frontend/src/pages/CandidateCenter/CandidateDetailDrawer.tsx`
- Modify: `frontend/src/services/candidates.ts`

- [ ] **Step 1: 契约测试**

```python
def test_patch_candidate_title(client, db_session, seeded_kb):
    candidate, *_ = _seed_document_candidate(db_session, seeded_kb)
    cid = f"doc_{candidate.candidate_id}"
    r = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}",
        headers={"X-Operator-Id": "admin"},
        json={"title": "修订标题"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["title"] == "修订标题"
```

- [ ] **Step 2: `candidate_edit_service.edit_candidate`** — 校验 pending + 写 audit `edit`

- [ ] **Step 3: PATCH 路由 + Pydantic `CandidatePatchRequest`**

- [ ] **Step 4: Drawer Form + `patchCandidate()`**

- [ ] **Step 5: pytest + 手动验证 + commit**

---

### Task P1-5: publish_validator 单元测试（US3）

**Files:**
- Create: `backend/tests/unit/test_candidate_publish_validator.py`
- Create: `backend/src/services/candidate_publish_validator.py`

- [ ] **Step 1: 测试 ku 缺 knowledge_type 失败**

```python
from src.services.candidate_publish_validator import validate_publish, PublishValidationError

def test_ku_requires_knowledge_type():
    with pytest.raises(PublishValidationError) as exc:
        validate_publish(confirm_as="ku", payload={"title": "t"}, view=mock_view)
    assert "knowledge_type" in str(exc.value)
```

- [ ] **Step 2: 实现校验**（active taxonomy/category、document 来源链、template 需 template_id）

- [ ] **Step 3: pytest PASS + commit**

---

### Task P1-6: KU publisher + confirm API（US3 首个 publisher）

**Files:**
- Create: `backend/src/services/publishers/ku_publisher.py`
- Create: `backend/src/services/candidate_publish_service.py`
- Create: `backend/tests/contract/test_candidate_confirm.py`
- Modify: `backend/src/api/routes/candidates.py`

- [ ] **Step 1: 契约测试 confirm ku**

```python
def test_confirm_candidate_as_ku(client, db_session, seeded_kb, seeded_category, seeded_taxonomy):
    candidate, file_import, document, node = _seed_document_candidate(db_session, seeded_kb)
    cid = f"doc_{candidate.candidate_id}"
    r = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/candidates/{cid}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "confirm_as": "ku",
            "knowledge_type": "solution",
            "product_category_ids": [str(seeded_category.category_id)],
            "chapter_taxonomy_id": str(seeded_taxonomy.taxonomy_id),
            "searchable": True,
            "review_comment": "test publish",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "published"
    assert data["confirmed_object_type"] == "ku"
    assert data["confirmed_object_id"]
```

- [ ] **Step 2: `ku_publisher.publish`** — INSERT `KnowledgeUnit` + 更新 candidate status + audit

- [ ] **Step 3: `candidate_publish_service.publish`** — 幂等检查 → validator → dispatch → commit

- [ ] **Step 4: POST `/confirm` 路由**

- [ ] **Step 5: pytest PASS + commit**

---

### Task P1-7: 其余 6 个 publisher（US3）

**Files:**
- Create: `backend/src/services/publishers/wiki_publisher.py`
- Create: `backend/src/services/publishers/template_chapter_publisher.py`
- Create: `backend/src/services/publishers/manual_asset_publisher.py`
- Create: `backend/src/services/publishers/chapter_pattern_publisher.py`
- Create: `backend/src/services/publishers/product_category_publisher.py`
- Create: `backend/src/services/publishers/ignore_handler.py`
- Extend: `backend/tests/contract/test_candidate_confirm.py`

对每个 `confirm_as` 增加一条 contract test（template stub → template_chapter；chapter_pattern 行 → confirmed；product_category → 新 category；ignore → rejected）。

- [ ] **Step 1: 写 6 个失败测试**（每个 confirm_as 一条）

- [ ] **Step 2: 实现 6 个 publisher**（参照 `ku_publisher` 事务边界）

- [ ] **Step 3: 注册到 `candidate_publish_service` dispatch 表**

- [ ] **Step 4: pytest `-k test_candidate_confirm` 全 PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(epic4): add all confirm_as publishers"
```

---

### Task P1-8: 发布集成测 + retry-publish（US3）

**Files:**
- Create: `backend/tests/integration/test_candidate_publish_flow.py`
- Modify: `backend/src/api/routes/candidates.py`

- [ ] **Step 1: 集成测试** — publish → GET KU 含 candidate_id → 重复 confirm 幂等 → retry-publish

- [ ] **Step 2: POST `/retry-publish` 复用 publish_service**

- [ ] **Step 3: pytest PASS + commit**

---

### Task P1-9: 正式资产只读 GET（US3）

**Files:**
- Modify: `backend/src/api/routes/knowledge_units.py`
- Modify: `backend/src/api/routes/wikis.py`
- Modify: `backend/src/api/routes/manual_assets.py`

- [ ] **Step 1: list/get 返回 candidate_id, import_id, source 字段**

- [ ] **Step 2: confirm ku 后 GET KU detail 断言来源链**

- [ ] **Step 3: Commit**

---

### Task P1-10: CandidateConfirmPage 全屏两栏 Tab（US3）

**Files:**
- Modify: `frontend/src/pages/CandidateCenter/CandidateConfirmPage.tsx`
- Modify: `frontend/src/services/candidates.ts`

- [ ] **Step 1: 布局** — 左栏 Descriptions + content；右栏 Tabs「编辑」「发布」

- [ ] **Step 2: 发布 Tab** — Select `confirm_as` 切换动态 Form 字段（见 design §5.3）

- [ ] **Step 3: 调用 `confirmCandidate()`；成功 message + navigate `/candidates`**

- [ ] **Step 4: 失败展示 error + 「重试」调用 `retryPublishCandidate()`**

- [ ] **Step 5: 手动验证 ku + ignore 路径 + commit**

**P1 Checkpoint（MVP）:** quickstart 场景 2–3 + 至少 ku/wiki/template_chapter 三类型发布演示

---

## Phase P2 — 治理效率（US4–US5，对应 T045–T055）

### Task P2-1: merge / split（US4）

**Files:**
- Create: `backend/tests/contract/test_candidate_merge_split.py`
- Create: `backend/src/services/candidate_merge_service.py`
- Modify: `backend/src/api/routes/candidates.py`
- Create: `frontend/src/pages/CandidateCenter/CandidateMergeModal.tsx`
- Create: `frontend/src/pages/CandidateCenter/CandidateSplitModal.tsx`

- [ ] **Step 1: 测试 merge 两条 pending → source.status=merged + lineage**

- [ ] **Step 2: 测试 split → N 条新 pending + 原候选 merged**

- [ ] **Step 3: 实现 service + POST routes + audit**

- [ ] **Step 4: 前端 Modal 接线**

- [ ] **Step 5: pytest + commit**

---

### Task P2-2: batch confirm / reject（US5）

**Files:**
- Create: `backend/tests/contract/test_candidate_batch.py`
- Modify: `backend/src/api/routes/candidate_batch.py`
- Create: `frontend/src/pages/CandidateCenter/BatchConfirmModal.tsx`
- Create: `frontend/src/pages/CandidateCenter/BatchResultDrawer.tsx`
- Modify: `frontend/src/pages/CandidateCenter/index.tsx`

- [ ] **Step 1: 测试 batch 部分失败** — 2 items，1 缺 knowledge_type → failed + 1 published

- [ ] **Step 2: `POST /candidates/batch/confirm` 逐条调用 publish_service，汇总 batch_id**

- [ ] **Step 3: `POST /candidates/batch/reject`**

- [ ] **Step 4: Modal 三策略 + Result Drawer 重试链接到 confirm 页**

- [ ] **Step 5: ProTable rowSelection + pytest + commit**

**P2 Checkpoint:** quickstart 场景 5–6 通过

---

## Phase P3 — 审计（US6，对应 T056–T059）

### Task P3-1: audit logs API + UI

**Files:**
- Create: `backend/tests/contract/test_candidate_audit_logs.py`
- Modify: `backend/src/api/routes/candidate_audit_logs.py`
- Create: `frontend/src/services/candidateAudit.ts`
- Modify: `frontend/src/pages/CandidateCenter/CandidateAuditPanel.tsx`
- Modify: `frontend/src/pages/CandidateCenter/index.tsx`

- [ ] **Step 1: 测试 publish 后按 candidate_id 查到 audit**

- [ ] **Step 2: GET 支持 candidate_id / batch_id / action / 时间范围**

- [ ] **Step 3: Audit Tab 或 `/candidates/audit` ProTable**

- [ ] **Step 4: pytest + commit**

**P3 Checkpoint:** spec 6 用户故事全部可验收

---

## Phase P4 — Polish（对应 T060–T063）

### Task P4-1: quickstart 全场景

- [ ] **Step 1: 按 `specs/006-candidate-confirm-workbench/quickstart.md` 场景 0–9 执行**

- [ ] **Step 2: 修复缺口 + commit**

### Task P4-2: 测试批跑 + Vitest

- [ ] **Step 1:**

```bash
cd backend && ../.venv/bin/pytest tests/ -k "candidate_confirm or candidate_publish or candidate_batch or candidate_edit or candidate_merge or candidate_audit" -v
```

- [ ] **Step 2: Vitest ConfirmPage smoke** — `CandidateConfirmPage.test.tsx` 切换 confirm_as 字段

- [ ] **Step 3: 更新 design doc Status → Approved**

---

## Spec Coverage Self-Review

| Spec 要求 | Plan Task |
|-----------|-----------|
| US1 列表筛选 | P1-1, P1-3 |
| US1 检索隔离 | P1-2 |
| US2 编辑 | P1-4 |
| US3 7 类型发布 + 幂等重试 | P1-5–P1-10 |
| US4 merge/split/ignore | P2-1 (+ ignore in P1-7) |
| US5 batch | P2-2 |
| US6 audit | P3-1 |
| FR-011 审计 | P0-3, 各写操作 task |
| SC-006 batch 30s | P2-2 性能 smoke in P4 |

无 TBD / 占位符。

---

## Execution Notes

- 测试数据库：SQLite in-memory（`conftest.py`）；enum 扩展后需 `create_all` 重建表
- 写操作 Header：`X-Operator-Id: admin`
- 复合 ID：API 层始终使用 `doc_` / `tpl_` 字符串
- 每个 Task 完成后单独 commit（便于 review / bisect）
- **MVP 停点：** P1-10 完成后可 demo；P2–P4 可后续 session 继续

**Maps to Spec Kit:** P0=T001–T015, P1=T016–T044, P2=T045–T055, P3=T056–T059, P4=T060–T063
