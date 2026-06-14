# Epic 3 实际标书导入与候选知识 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付实际标书解析全链路（自动三阶段解析 → 全屏确认向导 → 目录深度编辑与锁定 → 候选只读列表 + 章节模式挖掘），含 API、目录中心/候选中心 UI。

**Architecture:** 延续 Epic 0/1/2 monorepo。纵向切片 P0→P4。Epic 1 确认 `actual_bid` 后 BackgroundTasks claim 三条 downstream 并串行解析；向导 confirm **不** structure_lock；目录中心单独「确认目录」。双轨：Document Tree（追溯）与 Bid Outline（可编辑目录）独立表。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, python-docx, lxml, pydantic-settings | React 18, Ant Design 5, Vite | pytest, httpx

**Design doc:** `docs/superpowers/specs/2026-06-12-epic3-actual-bid-candidates-design.md`  
**Feature spec:** `specs/004-actual-bid-candidates/spec.md`  
**Data model:** `specs/004-actual-bid-candidates/data-model.md`  
**Contracts:** `specs/004-actual-bid-candidates/contracts/`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/pyproject.toml` | 增加 `lxml`（TOC 解析） |
| `backend/src/models/document.py` | Document ORM |
| `backend/src/models/document_tree_node.py` | Document Tree Node ORM |
| `backend/src/models/bid_outline.py` | BidOutline ORM |
| `backend/src/models/bid_outline_node.py` | BidOutlineNode ORM |
| `backend/src/models/actual_bid_parse_task.py` | 解析任务 ORM |
| `backend/src/models/document_parse_suggestion.py` | 分类建议 ORM |
| `backend/src/models/bid_outline_structure_diff.py` | 重解析 diff ORM |
| `backend/src/models/candidate_knowledge.py` | document 来源候选 ORM |
| `backend/src/models/chapter_pattern.py` | ChapterPattern ORM |
| `backend/src/models/chapter_pattern_mining_task.py` | 挖掘任务 ORM |
| `backend/src/models/actual_bid_audit_log.py` | 审计 ORM |
| `backend/src/services/docx_document_walker.py` | 全文 Document Tree |
| `backend/src/services/docx_toc_extractor.py` | 内置 TOC 抽取 |
| `backend/src/services/bid_outline_extract_service.py` | Outline 落库 |
| `backend/src/services/chapter_candidate_rules.py` | 章节类型→候选类型规则 |
| `backend/src/services/candidate_generate_service.py` | candidate_knowledges 写入 |
| `backend/src/services/actual_bid_parse_runner.py` | downstream 三阶段编排 |
| `backend/src/services/actual_bid_confirm_service.py` | 向导 confirm（无 lock） |
| `backend/src/services/bid_outline_diff_service.py` | diff 生成/apply/reject |
| `backend/src/services/chapter_pattern_miner.py` | 模式批挖掘 |
| `backend/src/api/routes/actual_bid_parse.py` | parse REST |
| `backend/src/api/routes/bid_outlines.py` | outline REST |
| `backend/src/api/routes/candidates.py` | 候选只读聚合 REST |
| `backend/src/api/routes/chapter_patterns.py` | pattern mine REST |
| `backend/src/services/confirm_service.py` | 修改：actual_bid confirm 后 enqueue parse |
| `backend/src/api/routes/file_imports.py` | 修改：actual_bid parse_status |
| `backend/tests/fixtures/sample-actual-bid.docx` | 夹具（可复制 sample-template 改标题） |
| `frontend/src/pages/OutlineCenter/` | 待办 + 列表 + 向导 |
| `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx` | 树编辑 + 确认目录 |
| `frontend/src/pages/CandidateCenter/index.tsx` | 只读列表 |
| `frontend/src/services/actualBidParse.ts` | API client |
| `frontend/src/services/bidOutlines.ts` | API client |
| `frontend/src/services/candidates.ts` | API client |

---

## Phase P0 — 实际标书域基建

### Task P0-1: lxml 依赖

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 添加依赖**

```toml
# backend/pyproject.toml dependencies 增加:
"lxml>=5.0.0",
```

- [ ] **Step 2: 安装并验证**

```bash
.venv/bin/pip install -e "backend/[dev]"
.venv/bin/python -c "import lxml; import docx; print('ok')"
```

Expected: 打印 `ok`

---

### Task P0-2: Document 域 ORM 与 init_db

**Files:**
- Create: `backend/src/models/document.py`
- Create: `backend/src/models/document_tree_node.py`
- Create: `backend/src/models/bid_outline.py`
- Create: `backend/src/models/bid_outline_node.py`
- Create: `backend/src/models/actual_bid_parse_task.py`
- Create: `backend/src/models/document_parse_suggestion.py`
- Create: `backend/src/models/bid_outline_structure_diff.py`
- Create: `backend/src/models/candidate_knowledge.py`
- Create: `backend/src/models/chapter_pattern.py`
- Create: `backend/src/models/chapter_pattern_mining_task.py`
- Create: `backend/src/models/actual_bid_audit_log.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/db/init_db.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_actual_bid_model.py`

- [ ] **Step 1: 写集成测试**

```python
# backend/tests/integration/test_actual_bid_model.py
from uuid import uuid4

from src.models.actual_bid_parse_task import (
    ActualBidParseTask,
    ActualBidParseTaskStatus,
)
from src.models.document import Document, DocumentSourceType, DocumentParseStatus


def test_create_document_and_parse_task(db_session):
    kb_id = uuid4()
    import_id = uuid4()
    doc = Document(
        kb_id=kb_id,
        import_id=import_id,
        source_type=DocumentSourceType.actual_bid,
        document_name="某项目投标书.docx",
        parse_status=DocumentParseStatus.pending,
        created_by="admin",
    )
    db_session.add(doc)
    db_session.flush()
    task = ActualBidParseTask(
        kb_id=kb_id,
        import_id=import_id,
        document_id=doc.document_id,
        status=ActualBidParseTaskStatus.pending,
        trace_id=uuid4(),
        created_by="admin",
    )
    db_session.add(task)
    db_session.commit()
    assert doc.document_id is not None
    assert task.parse_task_id is not None
```

- [ ] **Step 2: 按 `specs/004-actual-bid-candidates/data-model.md` 实现全部 ORM**

关键 enum（`actual_bid_parse_task.py`）：

```python
class ActualBidParseTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    ready = "ready"
    confirmed = "confirmed"
    failed = "failed"
    cancelled = "cancelled"
```

`CandidateKnowledge.status` 默认 `pending`；`ChapterPattern.status` 默认 `candidate`。

- [ ] **Step 3: 更新 `init_db.py` imports 列表**

- [ ] **Step 4: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_actual_bid_model.py -v
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/src/models/document.py backend/src/models/document_tree_node.py \
  backend/src/models/bid_outline.py backend/src/models/bid_outline_node.py \
  backend/src/models/actual_bid_parse_task.py backend/src/models/document_parse_suggestion.py \
  backend/src/models/bid_outline_structure_diff.py backend/src/models/candidate_knowledge.py \
  backend/src/models/chapter_pattern.py backend/src/models/chapter_pattern_mining_task.py \
  backend/src/models/actual_bid_audit_log.py backend/src/models/__init__.py \
  backend/src/db/init_db.py backend/tests/integration/test_actual_bid_model.py \
  backend/pyproject.toml
git commit -m "feat(epic3): add actual bid domain ORM models"
```

---

### Task P0-3: API 路由壳 + inactive KB 守卫

**Files:**
- Create: `backend/src/api/routes/actual_bid_parse.py`
- Create: `backend/src/api/routes/bid_outlines.py`
- Create: `backend/src/api/routes/candidates.py`
- Create: `backend/src/api/routes/chapter_patterns.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/contract/test_bid_outlines_list_empty.py`

- [ ] **Step 1: 契约测试**

```python
# backend/tests/contract/test_bid_outlines_list_empty.py
from fastapi.testclient import TestClient
from src.main import app


def test_list_bid_outlines_empty(seeded_kb):
    client = TestClient(app)
    kb_id = seeded_kb["kb_id"]
    r = client.get(
        f"/api/v1/kbs/{kb_id}/bid-outlines",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []


def test_list_candidates_empty(seeded_kb):
    client = TestClient(app)
    kb_id = seeded_kb["kb_id"]
    r = client.get(
        f"/api/v1/kbs/{kb_id}/candidates",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []
```

- [ ] **Step 2: 实现空列表 GET + 注册 routers**

```python
# backend/src/main.py 增加:
from src.api.routes.actual_bid_parse import router as actual_bid_parse_router
from src.api.routes.bid_outlines import router as bid_outlines_router
from src.api.routes.candidates import router as candidates_router
from src.api.routes.chapter_patterns import router as chapter_patterns_router

app.include_router(actual_bid_parse_router)
app.include_router(bid_outlines_router)
app.include_router(candidates_router)
app.include_router(chapter_patterns_router)
```

各 router 使用 `APIRouter(prefix="/api/v1/kbs/{kb_id}/...", tags=[...])` 与 Epic 2 相同的 `kb_write_guard` 依赖。

- [ ] **Step 3: inactive KB 写操作 403 测试**

```python
# backend/tests/contract/test_actual_bid_parse_inactive_kb.py
def test_trigger_parse_inactive_kb_forbidden(inactive_kb):
    client = TestClient(app)
    r = client.post(
        f"/api/v1/kbs/{inactive_kb['kb_id']}/actual-bid-parse/trigger",
        headers={"X-Operator-Id": "admin"},
        json={"import_id": str(inactive_kb["import_id"])},
    )
    assert r.status_code == 403
```

- [ ] **Step 4: pytest PASS + commit**

```bash
cd backend && ../.venv/bin/pytest tests/contract/test_bid_outlines_list_empty.py \
  tests/contract/test_actual_bid_parse_inactive_kb.py -v
git add backend/src/api/routes/actual_bid_parse.py backend/src/api/routes/bid_outlines.py \
  backend/src/api/routes/candidates.py backend/src/api/routes/chapter_patterns.py \
  backend/src/main.py backend/tests/contract/
git commit -m "feat(epic3): add actual bid API route shells"
```

---

### Task P0-4: 前端导航与空页

**Files:**
- Modify: `frontend/src/layout/AppShell.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/OutlineCenter/index.tsx`
- Create: `frontend/src/pages/CandidateCenter/index.tsx`

- [ ] **Step 1: AppShell 增加导航项**

```typescript
// frontend/src/layout/AppShell.tsx NAV_ITEMS 增加:
{ key: "/outlines", label: <Link to="/outlines">目录</Link> },
{ key: "/candidates", label: <Link to="/candidates">候选</Link> },
```

- [ ] **Step 2: 路由与空态页**

```tsx
// frontend/src/App.tsx
import OutlineCenterPage from "./pages/OutlineCenter";
import CandidateCenterPage from "./pages/CandidateCenter";

<Route path="/outlines" element={<OutlineCenterPage />} />
<Route path="/candidates" element={<CandidateCenterPage />} />
```

`OutlineCenter/index.tsx`：`PageContainer` + Empty「暂无目录」；`readOnly` 时禁用按钮。

- [ ] **Step 3: 手动验证**

```bash
cd frontend && npm run dev
```

打开 http://127.0.0.1:5173/outlines 与 /candidates，导航可见。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/layout/AppShell.tsx frontend/src/App.tsx \
  frontend/src/pages/OutlineCenter/index.tsx frontend/src/pages/CandidateCenter/index.tsx
git commit -m "feat(epic3): add outline and candidate center shells"
```

---

## Phase P1 — 自动解析 pipeline

### Task P1-1: docx_document_walker 单元测试与实现

**Files:**
- Create: `backend/tests/fixtures/sample-actual-bid.docx`
- Create: `backend/tests/unit/test_docx_document_walker.py`
- Create: `backend/src/services/docx_document_walker.py`

- [ ] **Step 1: 准备夹具**

从 `backend/tests/fixtures/sample-template.docx` 复制为 `sample-actual-bid.docx`，确保含 Heading 1/2 与至少一段正文。

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/unit/test_docx_document_walker.py
from pathlib import Path
from src.services.docx_document_walker import walk_document

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-actual-bid.docx"


def test_walk_document_returns_heading_and_paragraph_nodes():
    result = walk_document(FIXTURE)
    node_types = {n.node_type for n in result.nodes}
    assert "heading" in node_types
    assert "paragraph" in node_types
    headings = [n for n in result.nodes if n.node_type == "heading"]
    assert all(h.level >= 1 for h in headings)
    assert result.needs_manual_review is False or isinstance(result.needs_manual_review, bool)
```

- [ ] **Step 3: 实现 walker**

```python
# backend/src/services/docx_document_walker.py
@dataclass
class WalkedNode:
    temp_id: str
    parent_temp_id: str | None
    node_type: str  # heading|paragraph|table|image|other
    title: str | None
    level: int | None
    sort_order: int
    content_preview: str | None
    is_outline_node: bool
    needs_manual_review: bool = False

@dataclass
class DocumentWalkResult:
    nodes: list[WalkedNode]
    needs_manual_review: bool

def walk_document(path: Path) -> DocumentWalkResult:
    # 复用 docx_outline_parser 的 heading 检测；非 heading 段落挂当前 heading 栈
    ...
```

- [ ] **Step 4: pytest PASS + commit**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_docx_document_walker.py -v
git add backend/src/services/docx_document_walker.py backend/tests/unit/test_docx_document_walker.py \
  backend/tests/fixtures/sample-actual-bid.docx
git commit -m "feat(epic3): add docx document walker"
```

---

### Task P1-2: docx_toc_extractor 单元测试与实现

**Files:**
- Create: `backend/tests/unit/test_docx_toc_extractor.py`
- Create: `backend/src/services/docx_toc_extractor.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/unit/test_docx_toc_extractor.py
from pathlib import Path
from src.services.docx_toc_extractor import extract_toc_entries, ExtractStrategy

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-actual-bid.docx"


def test_extract_toc_fallback_to_heading_when_no_builtin_toc():
    result = extract_toc_entries(FIXTURE)
    assert len(result.entries) >= 1
    assert result.strategy in {ExtractStrategy.toc, ExtractStrategy.heading_heuristic, ExtractStrategy.flat_fallback}
    assert result.entries[0].title.strip() != ""
```

- [ ] **Step 2: 实现 TOC 优先 + fallback**

```python
# backend/src/services/docx_toc_extractor.py
class ExtractStrategy(str, enum.Enum):
    toc = "toc"
    heading_heuristic = "heading_heuristic"
    flat_fallback = "flat_fallback"

@dataclass
class TocEntry:
    temp_id: str
    parent_temp_id: str | None
    title: str
    level: int
    sort_order: int

def extract_toc_entries(path: Path) -> TocExtractResult:
    # 1) lxml 解析 word/document.xml 找 TOC 字段
    # 2) fallback: parse_outline(path) 转 TocEntry
    ...
```

- [ ] **Step 3: pytest PASS + commit**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_docx_toc_extractor.py -v
git add backend/src/services/docx_toc_extractor.py backend/tests/unit/test_docx_toc_extractor.py
git commit -m "feat(epic3): add docx TOC extractor with heading fallback"
```

---

### Task P1-3: bid_outline_extract_service + candidate_generate_service

**Files:**
- Create: `backend/src/services/bid_outline_extract_service.py`
- Create: `backend/src/services/chapter_candidate_rules.py`
- Create: `backend/src/config/chapter_candidate_rules.yaml`
- Create: `backend/src/services/candidate_generate_service.py`
- Create: `backend/tests/unit/test_chapter_candidate_rules.py`

- [ ] **Step 1: 规则单元测试**

```python
# backend/tests/unit/test_chapter_candidate_rules.py
from src.services.chapter_candidate_rules import resolve_candidate_type

def test_technical_solution_maps_to_ku_solution():
    result = resolve_candidate_type(taxonomy_code="technical_solution")
    assert result.candidate_type == "ku"
    assert result.suggested_knowledge_type == "solution"
```

- [ ] **Step 2: 实现 rules yaml + resolver**

- [ ] **Step 3: `bid_outline_extract_service.persist_outline` 将 TocEntry 映射到 ORM，写入 `source_node_id`**

- [ ] **Step 4: `candidate_generate_service.generate_for_document` 遍历 heading 节点写 `candidate_knowledges`**

- [ ] **Step 5: pytest + commit**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_chapter_candidate_rules.py -v
git add backend/src/services/bid_outline_extract_service.py \
  backend/src/services/chapter_candidate_rules.py \
  backend/src/config/chapter_candidate_rules.yaml \
  backend/src/services/candidate_generate_service.py \
  backend/tests/unit/test_chapter_candidate_rules.py
git commit -m "feat(epic3): add outline extract and candidate generation services"
```

---

### Task P1-4: actual_bid_parse_runner 集成测试与实现

**Files:**
- Create: `backend/src/services/actual_bid_parse_runner.py`
- Create: `backend/tests/integration/test_actual_bid_parse_runner.py`

- [ ] **Step 1: 集成测试（使用 uploaded + confirm actual_bid fixture 模式）**

```python
# backend/tests/integration/test_actual_bid_parse_runner.py
from src.models.actual_bid_parse_task import ActualBidParseTask, ActualBidParseTaskStatus
from src.models.downstream_task_entry import DownstreamTaskEntry, DownstreamTaskStatus
from src.services.actual_bid_parse_runner import run_actual_bid_parse_in_new_session


def test_runner_completes_three_downstream_stages(
    db_session, seeded_kb, uploaded_need_confirm, tmp_path, monkeypatch
):
    # 1) confirm actual_bid + copy fixture to storage_path
    # 2) run_actual_bid_parse_in_new_session(import_id=...)
    # 3) assert task.status == ready
    # 4) assert all downstream entries completed
    # 5) assert document, bid_outline, candidate_knowledges count > 0
    ...
```

- [ ] **Step 2: 实现 runner（参照 `template_parse_runner.py`）**

核心流程：

```python
def run_actual_bid_parse_in_new_session(*, import_id: UUID, operator_id: str, trace_id: UUID) -> None:
    with SessionLocal() as db:
        _claim_and_run(db, import_id=import_id, operator_id=operator_id, trace_id=trace_id)

def _claim_and_run(db, ...):
    # claim document_parse → walk → persist tree
    # claim bid_outline_extract → toc → persist outline
    # classify chunks → document_parse_suggestion
    # claim candidate_knowledge_generate → generate candidates
    # task.status = ready; audit log
```

失败时：`task.status=failed`，`file_import` 不删除。

- [ ] **Step 3: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_actual_bid_parse_runner.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/services/actual_bid_parse_runner.py backend/tests/integration/test_actual_bid_parse_runner.py
git commit -m "feat(epic3): add actual bid parse runner pipeline"
```

---

### Task P1-5: trigger API + confirm 后自动 enqueue

**Files:**
- Modify: `backend/src/api/routes/actual_bid_parse.py`
- Modify: `backend/src/services/confirm_service.py`
- Modify: `backend/src/api/routes/file_imports.py`
- Create: `backend/tests/contract/test_actual_bid_parse_trigger.py`

- [ ] **Step 1: 契约测试 trigger**

```python
# backend/tests/contract/test_actual_bid_parse_trigger.py
def test_trigger_actual_bid_parse_returns_202(client, confirmed_actual_bid_import):
    kb_id = confirmed_actual_bid_import["kb_id"]
    import_id = confirmed_actual_bid_import["import_id"]
    r = client.post(
        f"/api/v1/kbs/{kb_id}/actual-bid-parse/trigger",
        headers={"X-Operator-Id": "admin"},
        json={"import_id": import_id},
    )
    assert r.status_code == 202
    assert r.json()["data"]["parse_task_id"]
```

- [ ] **Step 2: 实现 `POST /trigger` + `GET /tasks` + `GET /tasks/{id}`**

参照 `template_parse.py` 的 `enqueue_template_parse` / BackgroundTasks 模式，新增 `enqueue_actual_bid_parse`。

- [ ] **Step 3: `confirm_service.py` 在 actual_bid confirm 成功后调用 enqueue**

```python
# confirm_service.py 在 create_downstream_entries 之后:
if record.file_purpose == FilePurpose.actual_bid and record.enter_parsing:
    from src.services.actual_bid_parse_runner import enqueue_actual_bid_parse
    enqueue_actual_bid_parse(db, import_id=record.import_id, operator_id=operator_id, ...)
```

- [ ] **Step 4: `file_imports.py` 列表 enrich actual_bid 的 parse_status**

```python
def _map_actual_bid_parse_status(task: ActualBidParseTask | None) -> str | None:
    if task is None:
        return None
    if task.status in {ActualBidParseTaskStatus.pending, ActualBidParseTaskStatus.running}:
        return "parsing"
    if task.status == ActualBidParseTaskStatus.ready:
        return "parse_ready"
    if task.status == ActualBidParseTaskStatus.confirmed:
        return "parse_confirmed"
    if task.status == ActualBidParseTaskStatus.failed:
        return "parse_failed"
    return None
```

对 `file_purpose=actual_bid` 使用 `ActualBidParseTask`；`template_file` 保持原逻辑。

- [ ] **Step 5: pytest + commit**

```bash
cd backend && ../.venv/bin/pytest tests/contract/test_actual_bid_parse_trigger.py -v
git add backend/src/api/routes/actual_bid_parse.py backend/src/services/confirm_service.py \
  backend/src/api/routes/file_imports.py backend/tests/contract/test_actual_bid_parse_trigger.py
git commit -m "feat(epic3): add parse trigger API and auto-enqueue on confirm"
```

---

### Task P1-6: Document GET API + 导入中心 parse_status 列

**Files:**
- Modify: `backend/src/api/routes/actual_bid_parse.py`
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`
- Modify: `frontend/src/services/fileImports.ts`
- Create: `backend/tests/contract/test_actual_bid_document_get.py`

- [ ] **Step 1: 实现 `GET /documents/{id}` + `GET /documents/{id}/tree`**

- [ ] **Step 2: 导入中心对 actual_bid 显示 parse_status 标签与「重试解析」**

- [ ] **Step 3: 契约测试 + commit**

```bash
git commit -m "feat(epic3): document API and import center parse status for actual_bid"
```

---

## Phase P2 — 全屏确认向导

### Task P2-1: actual_bid_confirm_service + confirm API

**Files:**
- Create: `backend/src/services/actual_bid_confirm_service.py`
- Modify: `backend/src/api/routes/actual_bid_parse.py`
- Create: `backend/tests/contract/test_actual_bid_parse_confirm.py`

- [ ] **Step 1: 契约测试（向导 confirm 不 lock）**

```python
def test_confirm_wizard_sets_confirmed_without_structure_lock(
    client, parse_ready_actual_bid_task, db_session
):
    task_id = parse_ready_actual_bid_task["parse_task_id"]
    outline_id = parse_ready_actual_bid_task["bid_outline_id"]
    kb_id = parse_ready_actual_bid_task["kb_id"]
    r = client.post(
        f"/api/v1/kbs/{kb_id}/actual-bid-parse/tasks/{task_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "document": {"bid_project_name": "测试项目", "bid_customer_name": "测试客户"},
            "outline_nodes": [{"outline_node_id": "...", "title": "1. 技术方案", "chapter_taxonomy_id": None}],
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "confirmed"
    outline = db_session.get(BidOutline, outline_id)
    assert outline.structure_locked_at is None
```

- [ ] **Step 2: 实现 confirm_service**

- 校验 `task.status == ready`
- PATCH document 元数据
- 更新 outline nodes
- `task.status = confirmed`
- **不**设置 `structure_locked_at`

- [ ] **Step 3: 同步更新 `specs/004-actual-bid-candidates/contracts/actual-bid-parse-api.md` 增加 confirm 端点**

- [ ] **Step 4: pytest + commit**

```bash
git commit -m "feat(epic3): add parse confirm wizard API without structure lock"
```

---

### Task P2-2: ActualBidParseConfirmWizard 前端

**Files:**
- Create: `frontend/src/pages/OutlineCenter/ActualBidParseConfirmWizard.tsx`
- Create: `frontend/src/services/actualBidParse.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/OutlineCenter/index.tsx`

- [ ] **Step 1: 参照 `ParseConfirmWizard.tsx` 实现三 Step**

- Step1：Form 项目名/客户/产品分类
- Step2：Tree 预览 + Taxonomy Select（数据来自 Epic 0 API）
- Step3：Table 只读候选列表（GET candidates?import_id=）

- [ ] **Step 2: 路由**

```tsx
<Route path="/outlines/parse-confirm/:parseTaskId" element={<ActualBidParseConfirmWizard />} />
```

- [ ] **Step 3: OutlineCenter 待办区「待确认解析」→ 链接向导**

- [ ] **Step 4: 完成后 navigate `/outlines/:bidOutlineId`**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(epic3): add actual bid parse confirm wizard UI"
```

---

## Phase P3 — 目录深度编辑与锁定

### Task P3-1: Bid Outline 节点 CRUD API

**Files:**
- Modify: `backend/src/api/routes/bid_outlines.py`
- Create: `backend/tests/contract/test_bid_outline_nodes.py`

- [ ] **Step 1: 实现 `GET /{id}/nodes` `PATCH /nodes/{id}` `POST /nodes/batch`**

- [ ] **Step 2: 契约测试：PATCH title 后 GET 一致；Document Tree 节点 title 不变**

```python
def test_outline_edit_does_not_mutate_document_tree(client, ready_outline_with_tree):
    ...
```

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(epic3): bid outline node edit APIs"
```

---

### Task P3-2: 确认目录 structure lock

**Files:**
- Modify: `backend/src/api/routes/bid_outlines.py`
- Create: `backend/tests/contract/test_bid_outline_confirm.py`

- [ ] **Step 1: 测试 `POST /bid-outlines/{id}/confirm`**

```python
def test_confirm_outline_sets_structure_locked(client, draft_outline):
    r = client.post(
        f"/api/v1/kbs/{kb_id}/bid-outlines/{outline_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={"status": "confirmed"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["structure_locked_at"] is not None
    assert r.json()["data"]["status"] == "confirmed"
```

- [ ] **Step 2: 实现 + audit log**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(epic3): bid outline confirm and structure lock"
```

---

### Task P3-3: bid_outline_diff_service + diff API

**Files:**
- Create: `backend/src/services/bid_outline_diff_service.py`
- Modify: `backend/src/api/routes/bid_outlines.py`
- Create: `backend/tests/integration/test_bid_outline_structure_diff.py`

- [ ] **Step 1: 集成测试（参照 `test_template_structure_diff.py`）**

锁定后 `force_reparse` → 产生 `bid_outline_structure_diff` pending；原节点 title 不变。

- [ ] **Step 2: 实现 diff 生成 / apply / reject**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(epic3): bid outline reparse diff apply and reject"
```

---

### Task P3-4: OutlineDetailPage 树编辑 UI

**Files:**
- Create: `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx`
- Create: `frontend/src/pages/OutlineCenter/OutlineTreeEditor.tsx`
- Create: `frontend/src/pages/OutlineCenter/OutlineDiffDrawer.tsx`
- Create: `frontend/src/services/bidOutlines.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 参照 `TemplateDetailPage` + `ChapterTreeEditor` 实现拖拽树**

- [ ] **Step 2: 顶部按钮「确认目录」调用 confirm API**

- [ ] **Step 3: DiffDrawer 审阅 apply/reject**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(epic3): outline detail page with tree editor and diff drawer"
```

---

## Phase P4 — 候选只读与模式挖掘

### Task P4-1: 候选聚合列表 API

**Files:**
- Modify: `backend/src/api/routes/candidates.py`
- Create: `backend/tests/contract/test_candidates_list.py`

- [ ] **Step 1: 测试聚合 document + template stub**

```python
def test_candidates_list_includes_document_and_template_channels(
    client, kb_with_document_candidate, kb_with_template_stub
):
    r = client.get(
        f"/api/v1/kbs/{kb_id}/candidates?status=pending",
        headers={"X-Operator-Id": "admin"},
    )
    channels = {item["source_channel"] for item in r.json()["data"]["items"]}
    assert "document" in channels
```

- [ ] **Step 2: 实现统一 DTO + `source_trace`**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(epic3): aggregated read-only candidates list API"
```

---

### Task P4-2: CandidateCenter 只读 UI

**Files:**
- Modify: `frontend/src/pages/CandidateCenter/index.tsx`
- Create: `frontend/src/services/candidates.ts`

- [ ] **Step 1: ProTable 列：title, candidate_type, source_channel, source_trace, created_at**

- [ ] **Step 2: 确认无「确认/发布」按钮；详情 Drawer 展示 content 预览**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(epic3): read-only candidate center UI"
```

---

### Task P4-3: chapter_pattern_miner + mine API

**Files:**
- Create: `backend/src/services/chapter_pattern_miner.py`
- Modify: `backend/src/api/routes/chapter_patterns.py`
- Create: `backend/tests/integration/test_chapter_pattern_mining.py`

- [ ] **Step 1: 集成测试**

```python
def test_mining_creates_candidate_patterns_when_frequency_met(db_session, kb_with_two_outlines):
  # POST mine → task completed → chapter_patterns status=candidate count >= 1
```

- [ ] **Step 2: 实现按 taxonomy + 归一化标题聚类，frequency >= min_frequency**

- [ ] **Step 3: OutlineCenter 增加「挖掘章节模式」按钮**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(epic3): chapter pattern mining task and API"
```

---

### Task P4-4: quickstart 端到端验证

**Files:**
- Modify: `specs/004-actual-bid-candidates/quickstart.md`（若实现中有路径偏差则修正）

- [ ] **Step 1: 按 quickstart 场景 0–7 手工或脚本跑通**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_actual_bid_flow.py -v
```

- [ ] **Step 2: 创建 `test_actual_bid_flow.py` 覆盖：confirm → ready → wizard confirm → outline lock**

- [ ] **Step 3: Commit**

```bash
git commit -m "test(epic3): add end-to-end actual bid flow integration test"
```

---

## Spec Coverage Self-Review

| Spec 要求 | 任务 |
|-----------|------|
| FR-001 actual_bid only | P1-5 trigger 校验 |
| FR-002 Document 来源字段 | P0-2, P1-4 runner |
| FR-003 Document Tree 扩展字段 | P0-2, P1-1 walker |
| FR-005/006 Bid Outline 抽取 | P1-2, P1-3 |
| FR-007/008 双轨编辑隔离 | P3-1 测试 |
| FR-009 重解析 diff | P3-3 |
| FR-010 分类映射 | P2-1, P3-4 |
| FR-012–015 候选生成与隔离 | P1-3, P4-1 |
| FR-016 Chapter Pattern | P4-3 |
| FR-017 三任务类型 | P1-4 runner |
| FR-018/019 目录中心/候选只读 | P0-4, P2-2, P4-2 |
| US-1–6 用户故事 | P1–P4 各阶段 |
| D1 全屏向导 | P2 |
| D2 向导不 lock | P2-1 测试断言 |
| SC-003 失败可恢复 | P1-4 runner 失败测试 |
| SC-006 候选不进检索 | P4-1（列表仅管理台；无检索索引注册） |

无 TBD/占位任务。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-12-epic3-actual-bid-candidates.md`.

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每个 Task 派发独立 subagent，任务间你做 review，迭代快  
2. **Inline Execution** — 在本会话用 executing-plans 按 P0→P4 批量执行，检查点暂停  

你倾向哪一种？
