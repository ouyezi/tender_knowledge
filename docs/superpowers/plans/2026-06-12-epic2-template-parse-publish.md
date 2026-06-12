# Epic 2 模板库解析与发布 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付模板文件解析全链路（自动解析 → 全屏确认向导 → 拖拽章节编辑 → 模板库发布），含 API、模板库中心 UI、Candidate stub 输出。

**Architecture:** 延续 Epic 0/1 monorepo。纵向切片 P0→P4。Epic 1 确认 `template_file` 后 BackgroundTasks claim `downstream_task_entries` 并 docx 解析；人工确认后锁定结构；发布写 snapshot。双入口：导入中心仅状态/重试，模板库中心主流程。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, python-docx, pydantic-settings | React 18, Ant Design 5, Vite | pytest, httpx

**Design doc:** `docs/superpowers/specs/2026-06-12-epic2-template-parse-publish-design.md`  
**Feature spec:** `specs/003-template-parse-publish/spec.md`  
**Contracts:** `specs/003-template-parse-publish/contracts/`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/pyproject.toml` | 增加 `python-docx` |
| `backend/src/models/template_library.py` | TemplateLibrary ORM |
| `backend/src/models/template.py` | Template ORM |
| `backend/src/models/template_chapter.py` | TemplateChapter ORM |
| `backend/src/models/template_material.py` | TemplateMaterial ORM |
| `backend/src/models/template_variable.py` | TemplateVariable ORM |
| `backend/src/models/template_rule.py` | TemplateRule ORM |
| `backend/src/models/template_parse_task.py` | 解析任务 ORM |
| `backend/src/models/template_parse_suggestion.py` | 机器建议 ORM |
| `backend/src/models/template_structure_diff.py` | 重解析 diff ORM |
| `backend/src/models/candidate_knowledge_stub.py` | Epic 4 占位 ORM |
| `backend/src/models/template_publish_snapshot.py` | 发布快照 ORM |
| `backend/src/models/template_audit_log.py` | 模板审计 ORM |
| `backend/src/models/classification_reference.py` | object_type 扩展 |
| `backend/src/services/docx_outline_parser.py` | docx 标题树 |
| `backend/src/services/docx_content_extractor.py` | Material 提取 |
| `backend/src/services/variable_detector.py` | `{{key}}` 扫描 |
| `backend/src/services/template_parse_runner.py` | claim + 解析编排 |
| `backend/src/services/template_confirm_service.py` | 向导 confirm |
| `backend/src/services/template_publish_service.py` | 发布校验 + snapshot |
| `backend/src/api/routes/template_parse.py` | parse REST |
| `backend/src/api/routes/template_libraries.py` | library REST |
| `backend/src/api/routes/templates.py` | template REST |
| `backend/src/api/routes/template_chapters.py` | chapter tree REST |
| `backend/src/api/routes/template_assets.py` | material/variable/rule REST |
| `backend/src/services/confirm_service.py` | 修改：confirm 后 enqueue parse |
| `backend/tests/unit/test_docx_outline_parser.py` | 解析单元测试 |
| `backend/tests/integration/test_template_parse_flow.py` | 端到端 |
| `backend/tests/contract/test_template_parse*.py` | API 契约 |
| `backend/tests/fixtures/sample-template.docx` | 已有夹具 |
| `frontend/src/pages/TemplateLibraryCenter/` | 待办 + 库列表 + 向导 |
| `frontend/src/pages/TemplateLibraryCenter/TemplateDetailPage.tsx` | 树编辑 + Tabs |
| `frontend/src/services/templates.ts` | API client |
| `frontend/src/pages/FileImportCenter/index.tsx` | parse_status 列 |

---

## Phase P0 — 模板域基建

### Task P0-1: python-docx 依赖

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: 添加依赖**

```toml
# backend/pyproject.toml dependencies 增加:
"python-docx>=1.1.0",
```

- [ ] **Step 2: 安装并验证 import**

```bash
.venv/bin/pip install -e "backend/[dev]"
.venv/bin/python -c "import docx; print(docx.__version__)"
```

Expected: 无 ImportError

---

### Task P0-2: Template 域 ORM 与 init_db

**Files:**
- Create: `backend/src/models/template_library.py`
- Create: `backend/src/models/template.py`
- Create: `backend/src/models/template_chapter.py`
- Create: `backend/src/models/template_material.py`
- Create: `backend/src/models/template_variable.py`
- Create: `backend/src/models/template_rule.py`
- Create: `backend/src/models/template_parse_task.py`
- Create: `backend/src/models/template_parse_suggestion.py`
- Create: `backend/src/models/template_structure_diff.py`
- Create: `backend/src/models/candidate_knowledge_stub.py`
- Create: `backend/src/models/template_publish_snapshot.py`
- Create: `backend/src/models/template_audit_log.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/models/classification_reference.py`
- Modify: `backend/src/db/init_db.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_template_model.py`

- [ ] **Step 1: 写集成测试**

```python
# backend/tests/integration/test_template_model.py
from uuid import uuid4
from src.models.template import Template, TemplateStatus, TemplateType
from src.models.template_parse_task import TemplateParseTask, TemplateParseTaskStatus

def test_create_template_and_parse_task(db_session):
    kb_id = uuid4()
    import_id = uuid4()
    tpl = Template(
        kb_id=kb_id,
        source_import_id=import_id,
        template_name="餐补模板.docx",
        template_type=TemplateType.technical_bid,
        status=TemplateStatus.draft,
        confirmed=False,
        created_by="admin",
    )
    db_session.add(tpl)
    db_session.flush()
    task = TemplateParseTask(
        kb_id=kb_id,
        import_id=import_id,
        template_id=tpl.template_id,
        status=TemplateParseTaskStatus.pending,
        trace_id=uuid4(),
    )
    db_session.add(task)
    db_session.commit()
    assert tpl.template_id is not None
    assert task.parse_task_id is not None
```

- [ ] **Step 2: 按 `specs/003-template-parse-publish/data-model.md` 实现全部 ORM**

关键 enum 示例：

```python
# backend/src/models/template_parse_task.py
class TemplateParseTaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    parse_ready = "parse_ready"
    confirmed = "confirmed"
    failed = "failed"
    cancelled = "cancelled"
```

- [ ] **Step 3: `classification_reference.py` 的 `ClassificationObjectType` 增加**

`template_library`, `template`, `template_chapter`, `template_material`

- [ ] **Step 4: 更新 init_db + conftest imports**

- [ ] **Step 5: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_template_model.py -v
```

---

### Task P0-3: API 路由壳

**Files:**
- Create: `backend/src/api/routes/template_parse.py`
- Create: `backend/src/api/routes/template_libraries.py`
- Create: `backend/src/api/routes/templates.py`
- Create: `backend/src/api/routes/template_chapters.py`
- Create: `backend/src/api/routes/template_assets.py`
- Modify: `backend/src/main.py`
- Create: `backend/tests/contract/test_template_libraries_list_empty.py`

- [ ] **Step 1: 契约测试**

```python
# backend/tests/contract/test_template_libraries_list_empty.py
from fastapi.testclient import TestClient
from src.main import app

def test_list_template_libraries_empty(seeded_kb):
    client = TestClient(app)
    kb_id = seeded_kb["kb_id"]
    r = client.get(
        f"/api/v1/kbs/{kb_id}/template-libraries",
        headers={"X-Operator-Id": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []
```

- [ ] **Step 2: 实现空列表 GET + parse tasks 空列表 + router 注册**

```python
# backend/src/main.py 增加:
from src.api.routes.template_parse import router as template_parse_router
from src.api.routes.template_libraries import router as template_libraries_router
# ... templates, template_chapters, template_assets
app.include_router(template_parse_router)
app.include_router(template_libraries_router)
```

Router prefix 对齐 contracts：

- `/api/v1/kbs/{kb_id}/template-parse`
- `/api/v1/kbs/{kb_id}/template-libraries`
- `/api/v1/kbs/{kb_id}/templates`

- [ ] **Step 3: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/contract/test_template_libraries_list_empty.py -v
```

---

### Task P0-4: 前端模板库中心壳层

**Files:**
- Create: `frontend/src/pages/TemplateLibraryCenter/index.tsx`
- Create: `frontend/src/services/templates.ts` (listLibraries stub)
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/layout/AppShell.tsx`

- [ ] **Step 1: 路由 `/template-libraries` + 导航「模板库」**

- [ ] **Step 2: 待办区 Card 空态 + Template Library Table 空态 + KB 未选 Alert**

```tsx
// frontend/src/pages/TemplateLibraryCenter/index.tsx 骨架
export default function TemplateLibraryCenterPage() {
  const { selectedKbId } = useKBContext();
  if (!selectedKbId) return <Alert message="请先选择知识库" type="info" />;
  return (
    <>
      <Card title="待处理">暂无待确认或失败的解析任务</Card>
      <Card title="模板库"><Table dataSource={[]} columns={[{ title: "名称", dataIndex: "library_name" }]} /></Card>
    </>
  );
}
```

- [ ] **Step 3: `npm run build` 通过**

---

### Task P0-5: 导入中心 parse_status 列占位

**Files:**
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`
- Modify: `frontend/src/services/fileImports.ts` (类型预留 `parse_status?`)

- [ ] **Step 1: Table 增加列 `parse_status`，默认显示 `—`**

- [ ] **Step 2: build 通过**

---

**Checkpoint P0:** 双导航可访问；模板 ORM 可建；空 API 200；inactive KB 写 403（复用 `kb_write_guard`）。

---

## Phase P1 — 自动解析 pipeline

### Task P1-1: docx_outline_parser 单元测试

**Files:**
- Create: `backend/src/services/docx_outline_parser.py`
- Create: `backend/tests/unit/test_docx_outline_parser.py`

- [ ] **Step 1: 失败测试**

```python
# backend/tests/unit/test_docx_outline_parser.py
from pathlib import Path
from src.services.docx_outline_parser import parse_outline

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-template.docx"

def test_parse_outline_returns_nodes():
    nodes = parse_outline(FIXTURE)
    assert len(nodes) >= 1
    assert all(n.title.strip() for n in nodes)
    assert all(n.level >= 1 for n in nodes)
    assert nodes[0].sort_order == 0
```

- [ ] **Step 2: 实现 `parse_outline(path) -> list[OutlineNode]`**

```python
# backend/src/services/docx_outline_parser.py
from dataclasses import dataclass
from pathlib import Path
import re
from docx import Document

HEADING_PREFIX = re.compile(r"^(\d+(?:\.\d+)*)[\s\.、]+")

@dataclass
class OutlineNode:
    temp_id: str
    parent_temp_id: str | None
    title: str
    level: int
    sort_order: int
    needs_manual_review: bool = False

def _is_heading(paragraph) -> int | None:
    name = (paragraph.style.name or "").lower()
    if name.startswith("heading"):
        try:
            return int(name.split()[-1])
        except ValueError:
            pass
    if "标题" in name:
        for ch in name:
            if ch.isdigit():
                return int(ch)
    return None

def parse_outline(docx_path: Path) -> list[OutlineNode]:
    doc = Document(str(docx_path))
    nodes: list[OutlineNode] = []
    stack: list[tuple[int, str]] = []
    sort_counters: dict[str | None, int] = {}
    idx = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        level = _is_heading(para)
        if level is None and HEADING_PREFIX.match(text):
            level = text.count(".") + 1 if "." in text.split()[0] else 1
        if level is None:
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_temp_id = stack[-1][1] if stack else None
        key = parent_temp_id
        sort_order = sort_counters.get(key, 0)
        sort_counters[key] = sort_order + 1
        temp_id = f"n{idx}"
        idx += 1
        nodes.append(
            OutlineNode(temp_id, parent_temp_id, text, level, sort_order)
        )
        stack.append((level, temp_id))
    if not nodes:
        nodes.append(OutlineNode("n0", None, "(待整理)", 1, 0, needs_manual_review=True))
    return nodes
```

- [ ] **Step 3: pytest PASS**

```bash
cd backend && ../.venv/bin/pytest tests/unit/test_docx_outline_parser.py -v
```

---

### Task P1-2: variable_detector + content_extractor

**Files:**
- Create: `backend/src/services/variable_detector.py`
- Create: `backend/src/services/docx_content_extractor.py`
- Create: `backend/tests/unit/test_variable_detector.py`

- [ ] **Step 1: 变量检测测试**

```python
from src.services.variable_detector import detect_variables

def test_detect_project_name():
    keys = detect_variables("项目名称：{{project_name}}")
    assert keys == ["project_name"]
```

- [ ] **Step 2: 实现**

```python
# backend/src/services/variable_detector.py
import re
VAR_PATTERN = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}")

def detect_variables(text: str) -> list[str]:
    return list(dict.fromkeys(VAR_PATTERN.findall(text or "")))
```

`docx_content_extractor.extract_materials(doc, outline_nodes)` 返回 material draft 列表（fixed_paragraph 类型 MVP）。

- [ ] **Step 3: pytest PASS**

---

### Task P1-3: template_parse_runner

**Files:**
- Create: `backend/src/services/template_parse_runner.py`
- Create: `backend/tests/integration/test_template_parse_runner.py`

- [ ] **Step 1: 集成测试（依赖 conftest：confirmed template_file import + storage）**

```python
def test_runner_claims_downstream_and_reaches_parse_ready(db_session, confirmed_template_import):
    from src.services.template_parse_runner import run_pending_template_parses
    run_pending_template_parses(db_session)
    task = db_session.query(TemplateParseTask).filter_by(
        import_id=confirmed_template_import["import_id"]
    ).one()
    assert task.status == TemplateParseTaskStatus.parse_ready
    assert task.template_id is not None
    suggestion = db_session.query(TemplateParseSuggestion).filter_by(
        parse_task_id=task.parse_task_id
    ).one()
    assert suggestion.suggested_chapter_tree
```

- [ ] **Step 2: 实现 runner**

核心逻辑：

1. `SELECT downstream_task_entries WHERE task_type=template_file_parse AND status=pending FOR UPDATE`
2. mark claimed → create `TemplateParseTask(running)`
3. load FileImport + FileStorage path
4. `parse_outline` + extract materials + detect variables
5. upsert Template draft + TemplateParseSuggestion JSON
6. task → `parse_ready`; downstream → `completed`
7. on error: task → `failed`; downstream → `failed`; **不修改 file_import**

- [ ] **Step 3: pytest PASS**

---

### Task P1-4: confirm 后自动 enqueue + parse API

**Files:**
- Modify: `backend/src/services/confirm_service.py`
- Modify: `backend/src/api/routes/file_imports.py` (BackgroundTasks)
- Modify: `backend/src/api/routes/template_parse.py`
- Create: `backend/tests/contract/test_template_parse_trigger.py`

- [ ] **Step 1: confirm template_file 后 BackgroundTasks 调用 runner**

在 `confirm_service.confirm_import` 成功创建 downstream 后：

```python
background_tasks.add_task(run_pending_template_parses, db_session_factory)
```

- [ ] **Step 2: 实现 GET `/template-parse/tasks`、GET `/tasks/{id}`、POST `/retry`**

- [ ] **Step 3: 契约测试：confirmed import 轮询至 parse_ready**

```bash
cd backend && ../.venv/bin/pytest tests/contract/test_template_parse_trigger.py tests/integration/test_template_parse_runner.py -v
```

---

### Task P1-5: 导入中心 parse_status + 重试

**Files:**
- Modify: `backend/src/api/routes/file_imports.py` (list/detail 增加 parse_status)
- Modify: `frontend/src/services/fileImports.ts`
- Modify: `frontend/src/pages/FileImportCenter/index.tsx`

- [ ] **Step 1: API 返回 `parse_status`: `running|parse_ready|failed|null`**

- [ ] **Step 2: 列表 Tag 展示；失败显示「重试」→ POST template-parse/retry；待确认链接 `/template-libraries?highlight={parseTaskId}`**

- [ ] **Step 3: 手动验证 quickstart 场景 0→1**

---

**Checkpoint P1:** Epic 1 确认 template_file 后自动 parse_ready；失败可 retry；sample docx 有章节树。

---

## Phase P2 — 解析确认向导

### Task P2-1: template_confirm_service + confirm API

**Files:**
- Create: `backend/src/services/template_confirm_service.py`
- Modify: `backend/src/api/routes/template_parse.py`
- Create: `backend/tests/contract/test_template_parse_confirm.py`

- [ ] **Step 1: 契约测试**

```python
def test_confirm_parse_task_locks_structure(api_client, seeded_kb, parse_ready_task):
    parse_task_id = parse_ready_task["parse_task_id"]
    kb_id = seeded_kb["kb_id"]
    r = api_client.post(
        f"/api/v1/kbs/{kb_id}/template-parse/tasks/{parse_task_id}/confirm",
        headers={"X-Operator-Id": "admin"},
        json={
            "template_library_id": None,
            "template_name": "餐补模板",
            "template_type": "technical_bid",
            "product_category_ids": [],
            "chapters": parse_ready_task["chapters_payload"],
            "materials": [],
            "candidate_actions": [],
        },
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "confirmed"
    assert r.json()["data"]["structure_locked_at"] is not None
```

- [ ] **Step 2: 实现 confirm：写 chapters/materials/stubs + lock + audit**

- [ ] **Step 3: 非 parse_ready confirm → 422 INVALID_STATE**

---

### Task P2-2: ParseConfirmWizard 全屏三 Step

**Files:**
- Create: `frontend/src/pages/TemplateLibraryCenter/ParseConfirmWizard.tsx`
- Modify: `frontend/src/App.tsx` (route `/template-libraries/parse-confirm/:parseTaskId`)
- Modify: `frontend/src/services/templates.ts`

- [ ] **Step 1: Step1 表单 — 库 Select/新建、产品分类、template_name/type**

- [ ] **Step 2: Step2 — Tree 预览编辑 ignore/required/章节类型（调 Epic 0 API）**

- [ ] **Step 3: Step3 — Material 表 + candidate ku/wiki 开关**

- [ ] **Step 4: 提交 confirm → navigate `/template-libraries/templates/:templateId`**

---

### Task P2-3: 模板库中心待办区

**Files:**
- Modify: `frontend/src/pages/TemplateLibraryCenter/index.tsx`
- Modify: `backend/src/api/routes/template_parse.py` (tasks list 支持 status filter)

- [ ] **Step 1: GET tasks `status=parse_ready|running|failed` 填充待办 Card**

- [ ] **Step 2: 「去确认」按钮 → `/parse-confirm/:id`**

- [ ] **Step 3: URL `?highlight=` 滚动高亮对应待办**

---

**Checkpoint P2:** 向导三 Step 可完成 confirm；structure_locked；未发布资产 status 仍为 draft。

---

## Phase P3 — 章节树与资产编辑

### Task P3-1: Chapter tree batch-update API

**Files:**
- Modify: `backend/src/api/routes/template_chapters.py`
- Create: `backend/tests/contract/test_template_chapter_batch_update.py`

- [ ] **Step 1: GET `/templates/{id}/chapters/tree` nested 格式**

- [ ] **Step 2: POST `/chapters/batch-update` 校验 level/parent 一致性**

```python
def test_batch_update_persists_tree(api_client, seeded_kb, confirmed_template):
    template_id = confirmed_template["template_id"]
    kb_id = seeded_kb["kb_id"]
    tree = api_client.get(
        f"/api/v1/kbs/{kb_id}/templates/{template_id}/chapters/tree",
        headers={"X-Operator-Id": "admin"},
    ).json()["data"]
    roots = tree["roots"]
    roots[0]["title"] = "1. 项目概述（改）"
    r = api_client.post(
        f"/api/v1/kbs/{kb_id}/templates/{template_id}/chapters/batch-update",
        headers={"X-Operator-Id": "admin"},
        json={"chapters": flatten_tree(roots)},
    )
    assert r.status_code == 200
```

- [ ] **Step 3: template_audit_log action=chapter_update**

---

### Task P3-2: ChapterTreeEditor + PropertyPanel

**Files:**
- Create: `frontend/src/pages/TemplateLibraryCenter/TemplateDetailPage.tsx`
- Create: `frontend/src/pages/TemplateLibraryCenter/ChapterTreeEditor.tsx`
- Create: `frontend/src/pages/TemplateLibraryCenter/ChapterPropertyPanel.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Tree `draggable` + `onDrop` 更新本地 state**

- [ ] **Step 2: 选中节点 → PropertyPanel 编辑 title/taxonomy/categories/required**

- [ ] **Step 3: Save → batch-update API → 刷新树**

---

### Task P3-3: Material / Variable / Rule Tabs

**Files:**
- Create: `frontend/src/pages/TemplateLibraryCenter/MaterialPanel.tsx`
- Create: `frontend/src/pages/TemplateLibraryCenter/VariableRulePanel.tsx`
- Modify: `backend/src/api/routes/template_assets.py`

- [ ] **Step 1: CRUD materials/variables/rules 对齐 `template-asset-api.md`**

- [ ] **Step 2: POST rules 拒绝 conditional/mutex/asset_required → 422**

- [ ] **Step 3: UI Tabs 联通 API**

---

**Checkpoint P3:** 拖拽+属性编辑保存后 GET tree 一致；变量 `{{project_name}}` 可配置。

---

## Phase P4 — 发布、stub、重解析 diff

### Task P4-1: template_publish_service

**Files:**
- Create: `backend/src/services/template_publish_service.py`
- Modify: `backend/src/api/routes/template_libraries.py`
- Modify: `backend/src/api/routes/templates.py`
- Create: `backend/tests/contract/test_template_publish.py`

- [ ] **Step 1: 发布校验测试 — 缺 required 章节 → PUBLISH_VALIDATION**

- [ ] **Step 2: 成功发布写 snapshot + status=published + version_no++**

- [ ] **Step 3: GET libraries?status=published 仅返回已发布**

---

### Task P4-2: candidate_knowledge_stubs 输出

**Files:**
- Modify: `backend/src/services/template_confirm_service.py`
- Modify: `backend/src/api/routes/template_assets.py` (GET candidate-stubs)

- [ ] **Step 1: confirm 时 `candidate_actions` accepted → INSERT stubs pending_confirm**

- [ ] **Step 2: GET `/templates/{id}/candidate-stubs?status=pending_confirm`**

- [ ] **Step 3: 集成断言 stub 含 import_id/template_chapter_id 溯源**

---

### Task P4-3: 重解析 structure diff

**Files:**
- Modify: `backend/src/services/template_parse_runner.py`
- Modify: `backend/src/api/routes/template_parse.py` (diff apply/reject)
- Create: `backend/tests/integration/test_template_structure_diff.py`

- [ ] **Step 1: locked template + force_reparse → diff pending_review，章节不变**

- [ ] **Step 2: POST diff/apply merge；POST reject 丢弃**

- [ ] **Step 3: 待办区「结构差异待审」入口（TemplateLibraryCenter）**

---

### Task P4-4: PublishModal + quickstart

**Files:**
- Create: `frontend/src/pages/TemplateLibraryCenter/PublishModal.tsx`
- Modify: `specs/003-template-parse-publish/quickstart.md` (若与实现偏差则更新)
- Modify: `docs/superpowers/specs/2026-06-12-epic2-template-parse-publish-design.md` (审批记录)

- [ ] **Step 1: PublishModal 展示校验错误/成功 snapshot_id**

- [ ] **Step 2: 跑通 quickstart 场景 0–4**

```bash
cd backend && ../.venv/bin/pytest -v -k template
```

- [ ] **Step 3: 更新 design doc §12 Superpowers plan 已生成**

---

**Checkpoint P4:** 发布后可查 snapshot；stubs 可查；diff 不覆盖锁定树；未发布库 Epic 5 查询为空。

---

## Spec Coverage Checklist

| Spec FR | Task |
|---------|------|
| FR-001 仅 template_file 解析 | P1-3, P1-4 |
| FR-002 标题树 + 编号排序 | P1-1 |
| FR-003 Material/Candidate 提取 | P1-2, P1-3 |
| FR-004 分类建议 | P1-3 (suggestion JSON) |
| FR-005 任务状态 + 失败不破坏 import | P1-3, P1-5 |
| FR-006 人工确认界面 | P2-1, P2-2 |
| FR-007 锁定后 diff | P4-3 |
| FR-008/009 Library/未归类 | P2-1, P2-2 |
| FR-010/011 章节/素材编辑 | P3-1, P3-2, P3-3 |
| FR-012/013 变量/规则 MVP | P1-2, P3-3 |
| FR-014/015/016 发布/版本/溯源 | P4-1 |
| FR-017 审计 | P2-1, P3-1, P4-1 |
| FR-018 未发布不可检索 | P4-1 |
| FR-019 模板库中心 | P0-4, P2-3, P3-2 |
| FR-020 不在范围项 | 全计划无 BidOutline/Instance |

---

## Execution Handoff

Plan complete. Choose:

1. **Subagent-Driven (recommended)** — 每 Task 派生子 agent + 阶段评审  
2. **Inline Execution** — 本会话按 Task 批量执行 + checkpoint

实现时 REQUIRED: `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`。
