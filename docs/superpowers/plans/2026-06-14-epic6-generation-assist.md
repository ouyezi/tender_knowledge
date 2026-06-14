# Epic 6 生成辅助升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Epic 5 模块组织建议之上，交付招标约束持久化、建议采纳门控、变量校验、Source Catalog LLM 章节草稿生成、Citation 绑定、Generation Snapshot 审计、accept/discard/regenerate 工作流及 OutlineCenter 向导 UI。

**Architecture:** `services/generation/` 分阶段管线 + 薄 `GenerationService` 编排；`InputPriorityResolver` 六层招标优先上下文；LLM 返回 JSON `source_ref_ids` → `CitationBinder`；`run_generation_task_in_new_session(task_id)` 精准 BackgroundTasks；append-only `generation_snapshots`。对齐 `docs/superpowers/specs/2026-06-14-epic6-generation-pipeline-design.md`。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL 15 | React 18, Ant Design 5, Vite | pytest, httpx | 复用 `llm_client.chat_completion`

**Design doc:** `docs/superpowers/specs/2026-06-14-epic6-generation-pipeline-design.md`  
**Feature spec:** `specs/008-generation-assist-upgrade/spec.md`  
**Spec Kit tasks:** `specs/008-generation-assist-upgrade/tasks.md` (T001–T072)  
**Data model:** `specs/008-generation-assist-upgrade/data-model.md`  
**Contracts:** `specs/008-generation-assist-upgrade/contracts/`

---

## File Map

| 路径 | 职责 |
|------|------|
| `backend/alembic/versions/*_epic6_generation.py` | 4 新表 + module_assembly_suggestions 扩展 |
| `backend/src/models/tender_requirement_context.py` | 外部招标约束（服务层） |
| `backend/src/models/generation_task.py` | 异步任务状态 |
| `backend/src/models/chapter_draft.py` | 草稿 + paragraphs JSON |
| `backend/src/models/generation_snapshot.py` | append-only 审计 |
| `backend/src/models/prompt_config_version.py` | generation-v1.0.0 prompt |
| `backend/src/models/module_assembly_suggestion.py` | **扩展** adoption 字段 |
| `backend/src/schemas/generation.py` | GenerationRequest、ResolvedContext、citation 类型 |
| `backend/src/services/generation/tender_requirement_service.py` | 招标约束 CRUD |
| `backend/src/services/generation/variable_resolver.py` | 必填校验 + `{{key}}` |
| `backend/src/services/generation/input_priority_resolver.py` | 六层 + source_catalog |
| `backend/src/services/generation/compliance_checker.py` | Manual Asset 合规消费 |
| `backend/src/services/generation/conditional_chapter_evaluator.py` | TemplateRule 评估 |
| `backend/src/services/generation/prompt_builder.py` | 版本化 prompt |
| `backend/src/services/generation/citation_binder.py` | ref_id → citation |
| `backend/src/services/generation/snapshot_writer.py` | 不可变 snapshot |
| `backend/src/services/generation/generation_service.py` | 编排 + run_task |
| `backend/src/services/generation/generation_runner.py` | `run_generation_task_in_new_session` |
| `backend/src/services/generation/prompt_seed.py` | seed generation-v1.0.0 |
| `backend/src/api/routes/tender_requirements.py` | `/tender-requirements` |
| `backend/src/api/routes/generation.py` | `/generation/*` |
| `backend/src/api/routes/module_suggestions.py` | **扩展** PATCH adoption |
| `backend/src/main.py` | 注册新 router |
| `frontend/src/services/tenderRequirements.ts` | API client |
| `frontend/src/services/generation.ts` | API client + 轮询 |
| `frontend/src/pages/OutlineCenter/TenderRequirementForm.tsx` | 约束录入 |
| `frontend/src/pages/OutlineCenter/VariableFillPanel.tsx` | 变量填写 |
| `frontend/src/pages/OutlineCenter/ChapterDraftPanel.tsx` | 草稿 + 工作流 |
| `frontend/src/pages/OutlineCenter/SnapshotDetailDrawer.tsx` | 快照审计 |
| `frontend/src/pages/OutlineCenter/ModuleSuggestionWizard.tsx` | **扩展** 采纳步 |
| `backend/tests/integration/test_epic6_quickstart_flow.py` | mock LLM 端到端 |
| `backend/tests/integration/test_generation_conflict_priority.py` | 冲突优先级 |

---

## Phase P0 — 基建（T001–T016，阻塞）

### Task P0-1: 路由与前端壳（T001–T004）

**Files:**
- Modify: `backend/src/main.py`
- Create: `frontend/src/services/tenderRequirements.ts`
- Create: `frontend/src/services/generation.ts`
- Create: `frontend/src/pages/OutlineCenter/TenderRequirementForm.tsx`
- Create: `frontend/src/pages/OutlineCenter/VariableFillPanel.tsx`
- Create: `frontend/src/pages/OutlineCenter/ChapterDraftPanel.tsx`

- [ ] **Step 1:** 在 `main.py` 注册空 router：

```python
from src.api.routes.tender_requirements import router as tender_requirements_router
from src.api.routes.generation import router as generation_router

app.include_router(tender_requirements_router)
app.include_router(generation_router)
```

- [ ] **Step 2:** 创建 `tender_requirements.py` / `generation.py` 仅含 `APIRouter` 与 `prefix`（无 handler 亦可启动）。

- [ ] **Step 3:** 前端三个组件 export 空壳 `export function TenderRequirementForm() { return null }`。

- [ ] **Step 4:** 验证启动：

```bash
./scripts/start.sh
curl -s http://127.0.0.1:8000/health
```

Expected: `200`

### Task P0-2: Migration + ORM（T005–T012）

**Files:**
- Create: `backend/alembic/versions/20260615_1000_epic6_generation.py`
- Create: `backend/src/models/tender_requirement_context.py`
- Create: `backend/src/models/generation_task.py`
- Create: `backend/src/models/chapter_draft.py`
- Create: `backend/src/models/generation_snapshot.py`
- Create: `backend/src/models/prompt_config_version.py`
- Modify: `backend/src/models/module_assembly_suggestion.py`
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/db/init_db.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_epic6_models.py`

- [ ] **Step 1: 写模型集成测试**

```python
# backend/tests/integration/test_epic6_models.py
from uuid import uuid4

from src.models.generation_task import GenerationTask, GenerationTaskStatus


def test_create_generation_task(db_session, seeded_kb):
    task = GenerationTask(
        kb_id=seeded_kb.kb_id,
        requirement_context_id=uuid4(),
        target_outline_node={"title": "1.1 总体架构", "level": 2, "sort_order": 1},
        status=GenerationTaskStatus.pending,
        request_snapshot={"variable_values": {}},
        created_by="tester",
    )
    db_session.add(task)
    db_session.commit()
    assert task.task_id is not None
```

- [ ] **Step 2:** Alembic `down_revision = "20260614_1500"`，创建表：

  - `tender_requirement_contexts`
  - `generation_tasks`（status enum: pending/running/completed/failed）
  - `chapter_drafts`（outcome_status: pending/accepted/discarded）
  - `generation_snapshots`
  - `prompt_config_versions`
  - `ALTER module_assembly_suggestions ADD` requirement_context_id, status, adoption_reason, adopted_by, adopted_at

- [ ] **Step 3:** 实现 ORM；`ModuleAssemblySuggestion.status` enum：`draft` | `adopted` | `rejected`。

- [ ] **Step 4:** 注册 `conftest.py` imports；运行：

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_epic6_models.py -v
```

Expected: PASS

### Task P0-3: Schemas + Prompt Seed（T013–T014）

**Files:**
- Create: `backend/src/schemas/generation.py`
- Create: `backend/src/services/generation/prompt_seed.py`
- Create: `backend/src/services/generation/__init__.py`
- Create: `backend/tests/unit/test_prompt_seed.py`

- [ ] **Step 1: 失败单测**

```python
# backend/tests/unit/test_prompt_seed.py
from src.services.generation.prompt_seed import GENERATION_PROMPT_VERSION


def test_generation_prompt_version_is_v1():
    assert GENERATION_PROMPT_VERSION == "generation-v1.0.0"
```

- [ ] **Step 2:** 定义 schemas：

```python
# backend/src/schemas/generation.py (摘要)
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID

class GenerationTaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class SourceCatalogEntry(BaseModel):
    ref_id: str
    type: str  # ku | wiki | template_chapter | manual_asset | tender_rejection | tender_score | variable
    object_id: str | None = None
    title: str
    excerpt: str

class ResolvedGenerationContext(BaseModel):
    layers: dict[str, list[str]]
    source_catalog: list[SourceCatalogEntry]
    conflict_pre_flags: list[dict] = Field(default_factory=list)
```

- [ ] **Step 3:** `prompt_seed.py` 含 `GENERATION_PROMPT_VERSION` 与 system/user 模板字符串（要求 JSON + source_ref_ids）。

- [ ] **Step 4:** `seed_generation_prompt(db, kb_id)` 写入 `prompt_config_versions` 若不存在。

**Checkpoint P0:** migration 成功；models import；prompt seed 单测 PASS。

---

## Phase P1 — US1 招标约束 + 建议采纳（T017–T022）

### Task P1-1: Tender Requirement CRUD

**Files:**
- Create: `backend/src/services/generation/tender_requirement_service.py`
- Create: `backend/src/api/routes/tender_requirements.py`
- Create: `backend/tests/contract/test_tender_requirement_crud.py`

- [ ] **Step 1: 契约测试**

```python
# backend/tests/contract/test_tender_requirement_crud.py
def test_create_and_get_tender_requirement(client, seeded_kb):
    create = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/tender-requirements",
        json={
            "title": "Epic6 测试约束",
            "outline_nodes": [{"title": "1.1 总体架构", "level": 2, "sort_order": 1}],
            "score_points": [{"node_ref": "1.1", "text": "架构清晰"}],
            "rejection_clauses": ["未提供资质证明废标"],
        },
        headers={"X-Operator-Id": "tester"},
    )
    assert create.status_code == 200
    ctx_id = create.json()["data"]["requirement_context_id"]
    get_resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/tender-requirements/{ctx_id}",
        headers={"X-Operator-Id": "tester"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["title"] == "Epic6 测试约束"
```

- [ ] **Step 2:** 实现 `TenderRequirementService.create/get/list/archive`。

- [ ] **Step 3:** 422 当 `outline_nodes` 为空。

- [ ] **Step 4:** 跑测试 PASS。

### Task P1-2: Module Suggestion Adoption（T021–T022）

**Files:**
- Modify: `backend/src/services/retrieval/module_suggestion/module_suggestion_service.py`
- Modify: `backend/src/api/routes/module_suggestions.py`
- Create: `backend/tests/contract/test_module_suggestion_adoption.py`

- [ ] **Step 1: 契约测试**

```python
def test_adopt_module_suggestion(client, seeded_kb, db_session):
    # 先 POST module-suggestions（复用 test_module_suggestion fixture 模式）
    suggestion_id = "..."  # from create response
    resp = client.patch(
        f"/api/v1/kbs/{seeded_kb.kb_id}/module-suggestions/{suggestion_id}/adoption",
        json={"status": "adopted", "adoption_reason": "测试采纳"},
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "adopted"
```

- [ ] **Step 2:** `ModuleSuggestionService.adopt(kb_id, suggestion_id, status, reason, operator_id)` 更新 status/adopted_at。

- [ ] **Step 3:** `create_suggestions` 可选接受 `requirement_context_id`，写入行 + `tender_context_snapshot`。

**Checkpoint P1:** quickstart 场景 1–2 API 通过。

---

## Phase P2 — US2 变量校验（T023–T027）

### Task P2-1: VariableResolver

**Files:**
- Create: `backend/src/services/generation/variable_resolver.py`
- Create: `backend/tests/unit/test_variable_resolver.py`
- Create: `backend/tests/contract/test_generation_drafts_validation.py`

- [ ] **Step 1: 单元测试**

```python
# backend/tests/unit/test_variable_resolver.py
import pytest
from src.services.generation.variable_resolver import VariableResolver, MissingRequiredVariablesError
from src.models.template_variable import TemplateVariable, TemplateVariableValueType


def test_missing_required_raises():
    resolver = VariableResolver()
    variables = [
        TemplateVariable(variable_key="project_name", required=True, default_value=None),
    ]
    with pytest.raises(MissingRequiredVariablesError) as exc:
        resolver.validate_and_resolve(variables=variables, values={})
    assert "project_name" in exc.value.missing_keys


def test_placeholder_replace():
    resolver = VariableResolver()
    text = resolver.replace_placeholders(
        "项目：{{project_name}}",
        resolved={"project_name": "智慧园区"},
    )
    assert text == "项目：智慧园区"
```

- [ ] **Step 2:** 实现 `validate_and_resolve`、`collect_for_template_chapters(db, chapter_ids)`、`replace_placeholders`。

- [ ] **Step 3: 契约测试** — `POST /generation/drafts` stub route 调用预检，缺必填 → 422：

```python
def test_create_draft_missing_variables_returns_422(client, seeded_kb):
    resp = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/generation/drafts",
        json={"...": "..."},  # adopted suggestion + empty variable_values
        headers={"X-Operator-Id": "tester"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MISSING_REQUIRED_VARIABLES"
```

- [ ] **Step 4:** PASS。

**Checkpoint P2:** 变量门控可独立验收，无需 LLM。

---

## Phase P3 — US3 章节草稿生成核心（T028–T041）🎯 MVP 停点

### Task P3-1: InputPriorityResolver

**Files:**
- Create: `backend/src/services/generation/input_priority_resolver.py`
- Create: `backend/tests/unit/test_input_priority_resolver.py`

- [ ] **Step 1: 失败单测**

```python
def test_rejection_layer_listed_before_template_hints():
    from src.services.generation.input_priority_resolver import InputPriorityResolver

    ctx = InputPriorityResolver().resolve(
        rejection_clauses=["未提供资质证明废标"],
        score_points=[{"node_ref": "1.1", "text": "架构清晰"}],
        outline_structure={"max_level": 3},
        user_selections=[],
        knowledge_pack_items=[{"title": "KU-A", "object_id": "uuid-ku"}],
        template_hints=[{"title": "模板章", "object_id": "uuid-tpl"}],
        conflict_template_ids=set(),
    )
    assert ctx.layers["L1_rejection"]
    assert ctx.source_catalog[0].ref_id.startswith("SRC-") or ctx.source_catalog[0].ref_id.startswith("TREQ-")
    # 冲突 template 不应出现在 catalog
    tpl_ids = {e.object_id for e in ctx.source_catalog if e.type == "template_chapter"}
    assert "uuid-tpl" not in tpl_ids or "uuid-tpl" not in (conflict set applied separately)
```

- [ ] **Step 2:** 实现六层 + `source_catalog` 编号（SRC-001…, TREQ-SP-0…, VAR-key）。

- [ ] **Step 3:** 传入 `conflict_template_ids` 时排除 L6 hints。

### Task P3-2: CitationBinder

**Files:**
- Create: `backend/src/services/generation/citation_binder.py`
- Create: `backend/tests/unit/test_citation_binder.py`

- [ ] **Step 1: 失败单测**

```python
def test_bind_paragraph_citations_from_ref_ids():
    from src.services.generation.citation_binder import CitationBinder
    from src.schemas.generation import SourceCatalogEntry

    catalog = [
        SourceCatalogEntry(ref_id="SRC-001", type="ku", object_id="ku-uuid", title="KU-A", excerpt="摘要"),
    ]
    paragraphs = CitationBinder().bind(
        llm_paragraphs=[{"text": "正文", "source_ref_ids": ["SRC-001"]}],
        catalog=catalog,
        resolved_variables={},
    )
    assert len(paragraphs[0]["citations"]) >= 1
    assert paragraphs[0]["citations"][0]["source_type"] == "ku"
    assert paragraphs[0]["citations"][0]["source_id"] == "ku-uuid"
```

- [ ] **Step 2:** 未知 ref_id → orphan warning 字段；空 ref_ids → tender 兜底 citation。

### Task P3-3: PromptBuilder + LLM JSON 解析

**Files:**
- Create: `backend/src/services/generation/prompt_builder.py`
- Create: `backend/src/services/generation/compliance_checker.py`
- Create: `backend/tests/unit/test_prompt_builder.py`

- [ ] **Step 1:** `PromptBuilder.build(resolved: ResolvedGenerationContext) -> tuple[str, str]` 返回 (system, user)。

- [ ] **Step 2:** `ComplianceChecker.filter(catalog, compliance[])` 移除 fail/missing manual assets。

- [ ] **Step 3:** `parse_llm_json(content: str) -> dict` — strip fence + json.loads + 一次 repair 钩子（可 mock）。

### Task P3-4: GenerationService + Runner

**Files:**
- Create: `backend/src/services/generation/snapshot_writer.py`
- Create: `backend/src/services/generation/generation_service.py`
- Create: `backend/src/services/generation/generation_runner.py`
- Create: `backend/src/api/routes/generation.py`
- Create: `backend/tests/contract/test_generation_drafts.py`
- Create: `backend/tests/integration/test_epic6_quickstart_flow.py`

- [ ] **Step 1: mock LLM 集成测试**

```python
# backend/tests/integration/test_epic6_quickstart_flow.py
from unittest.mock import patch
from src.services.llm_client import LLMResponse

MOCK_LLM_JSON = '''
{"paragraphs":[{"text":"总体架构说明","source_ref_ids":["SRC-001"]}]}
'''

@patch("src.services.generation.generation_service.chat_completion")
def test_generation_task_completes_with_mock_llm(mock_llm, client, seeded_kb, epic6_seed):
    mock_llm.return_value = LLMResponse(content=MOCK_LLM_JSON, model="test", provider="mock")
    create = client.post(f"/api/v1/kbs/{seeded_kb.kb_id}/generation/drafts", json={...})
    task_id = create.json()["data"]["task_id"]
    # 同步测试：直接调用 runner 或轮询
    from src.services.generation.generation_runner import run_generation_task_in_new_session
    run_generation_task_in_new_session(task_id)
    status = client.get(f"/api/v1/kbs/{seeded_kb.kb_id}/generation/tasks/{task_id}")
    assert status.json()["data"]["status"] == "completed"
```

- [ ] **Step 2:** `GenerationService.run_task(task_id)` 管线顺序（design doc §4.1）。

- [ ] **Step 3:** `generation_runner.py`：

```python
def run_generation_task_in_new_session(task_id: UUID) -> None:
    db = SessionLocal()
    try:
        GenerationService(db).run_task(task_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

- [ ] **Step 4:** `POST /generation/drafts` — 同步门控 → insert pending → `background_tasks.add_task(run_generation_task_in_new_session, task_id)` → 202。

- [ ] **Step 5:** `ConflictDetector` 后检写入 `conflict_hints`；`SnapshotWriter.write` append-only。

- [ ] **Step 6:** `conftest.py` 添加 `epic6_seed` fixture（tender context + adopted suggestion + template variable）。

**Checkpoint P3（MVP）:** mock LLM 端到端；quickstart 场景 3–4；`pytest -k epic6` 绿。

---

## Phase P4 — US4 快照查询（T042–T046）

### Task P4-1: Draft & Snapshot GET

**Files:**
- Modify: `backend/src/api/routes/generation.py`
- Create: `backend/tests/contract/test_generation_snapshots.py`

- [ ] **Step 1: 契约测试**

```python
def test_get_snapshot_contains_prompt_version_and_variables(client, seeded_kb, completed_draft_fixture):
    snap_id = completed_draft_fixture["snapshot_id"]
    resp = client.get(
        f"/api/v1/kbs/{seeded_kb.kb_id}/generation/snapshots/{snap_id}",
        headers={"X-Operator-Id": "tester"},
    )
    data = resp.json()["data"]
    assert data["prompt_version"] == "generation-v1.0.0"
    assert "variable_inputs" in data
    assert data["requirement_context_snapshot"]
```

- [ ] **Step 2:** `GET /drafts/{draft_id}` 返回 paragraphs + citations。

- [ ] **Step 3:** `GET /drafts` 与 `GET /snapshots` 列表分页 query。

- [ ] **Step 4:** `snapshot_writer` 写入 `retrieval_trace_summary`（来自 suggestion.trace_id）。

**Checkpoint P4:** quickstart 场景 5 通过。

---

## Phase P5 — US5 条件章节（T047–T051）

### Task P5-1: ConditionalChapterEvaluator

**Files:**
- Create: `backend/src/services/generation/conditional_chapter_evaluator.py`
- Create: `backend/tests/unit/test_conditional_chapter_evaluator.py`
- Create: `backend/tests/integration/test_generation_conflict_priority.py`

- [ ] **Step 1: 单测** — product_match rule + 招标关键词匹配 → suggested enable。

- [ ] **Step 2:** 集成测试 — 冲突 template citation → `conflict_hints` 非空；L6 预检已排除。

- [ ] **Step 3:** `user_chapter_selections` 写入 request_snapshot 与 snapshot。

**Checkpoint P5:** SC-003 / SC-007 冲突场景可测。

---

## Phase P6 — US6 工作流（T052–T057）

### Task P6-1: Accept / Discard / Regenerate

**Files:**
- Modify: `backend/src/api/routes/generation.py`
- Modify: `backend/src/services/generation/generation_service.py`
- Create: `backend/tests/contract/test_generation_workflow.py`

- [ ] **Step 1: 契约测试**

```python
def test_accept_then_regenerate_creates_new_task(client, seeded_kb, completed_draft_fixture):
    draft_id = completed_draft_fixture["draft_id"]
    accept = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/generation/drafts/{draft_id}/accept",
        headers={"X-Operator-Id": "tester"},
    )
    assert accept.json()["data"]["outcome_status"] == "accepted"
    regen = client.post(
        f"/api/v1/kbs/{seeded_kb.kb_id}/generation/drafts/{draft_id}/regenerate",
        json={"variable_values": {"project_name": "v2"}},
        headers={"X-Operator-Id": "tester"},
    )
    assert regen.status_code in (200, 202)
    assert regen.json()["data"]["task_id"] != completed_draft_fixture["task_id"]
```

- [ ] **Step 2:** accept 时同 target 旧 accepted 稿 `is_active=false`。

- [ ] **Step 3:** discard 不改 snapshot；regenerate 新 version_tag（v2, v3…）。

**Checkpoint P6:** quickstart 场景 6 通过。

---

## Phase P7 — OutlineCenter UI（T058–T066）

### Task P7-1: 向导 UI

**Files:**
- Modify: `frontend/src/pages/OutlineCenter/ModuleSuggestionWizard.tsx`
- Modify: `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx`
- Implement: `TenderRequirementForm.tsx`, `VariableFillPanel.tsx`, `ChapterDraftPanel.tsx`, `SnapshotDetailDrawer.tsx`
- Implement: `tenderRequirements.ts`, `generation.ts`

- [ ] **Step 1:** Wizard 步骤：约束 → 建议 → **采纳** → 变量 → 生成（轮询 task）→ 草稿预览。

- [ ] **Step 2:** `ChapterDraftPanel` 展示 paragraphs citations + conflict_hints；按钮 accept/discard/regenerate。

- [ ] **Step 3:** `SnapshotDetailDrawer` 展示 prompt_version、variable_inputs、used_*_ids。

- [ ] **Step 4:** 手动走 quickstart UI 验证清单（plan quickstart §UI）。

**Checkpoint P7:** 6 个用户故事 UI 可验收。

---

## Phase P8 — Polish（T067–T072）

### Task P8-1: quickstart + 全量测试

**Files:**
- Modify: `backend/tests/contract/test_generation_drafts.py`
- Modify: `backend/tests/integration/test_epic6_quickstart_flow.py`

- [ ] **Step 1:** 跑 `specs/008-generation-assist-upgrade/quickstart.md` 场景 0–7，修缺口。

- [ ] **Step 2:** `LLM_UNAVAILABLE` 契约 — `settings.llm_api_key` 空时 POST drafts → 503。

- [ ] **Step 3:** 未发布资产引用 → 422 `ASSET_NOT_PUBLISHED`。

- [ ] **Step 4:**

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k "tender_requirement or generation or epic6"
```

Expected: all PASS

- [ ] **Step 5:** `snapshot_writer.py` 顶部注释 G4 字段对照 FR-010（审计清单）。

**Checkpoint P8:** 生产就绪；Constitution G1–G6 可核对。

---

## Spec Coverage Checklist

| Spec / FR | 任务 |
|-----------|------|
| FR-001 招标约束 | P1-1 |
| FR-002–FR-003 模块建议 + 采纳 | P1-2 |
| FR-004 模板变量 | P2-1 |
| FR-005 条件章节 | P5-1 |
| FR-006–FR-009 多源输入/优先级/冲突 | P3-1, P3-4, P5-1 |
| FR-010 Generation Snapshot | P3-4, P4-1 |
| FR-011 创建/查询/重新生成/接受废弃 | P3-4, P6-1 |
| FR-012 Epic 5 衔接 | P1-2 |
| FR-013 候选隔离 | P8-1 ASSET_NOT_PUBLISHED |
| SC-001 ≤3min 生成 | P3-4（live LLM 手动探针） |
| SC-002 100% 段落 citation | P3-2, P3-4 |
| SC-003 冲突提示 | P3-4, P5-1 |
| SC-005 变量拦截 | P2-1 |
| US1–US6 用户故事 | P1–P7 |

---

## Self-Review（2026-06-14）

| 检查 | 结果 |
|------|------|
| Spec 每条 FR 有对应 Task | ✅ 见上表 |
| TBD / TODO / “implement later” | 无 |
| 类型/命名跨 Task 一致 | `ResolvedGenerationContext`, `GenerationTaskStatus`, `run_generation_task_in_new_session(task_id)` 全文统一 |
| 范围 | 单管线；Template Instance / 招标解析未纳入 |
| 与 design doc 一致 | Source Catalog + task_id runner + 双阶段 conflict ✅ |

---

## Execution Order

```text
P0 → P1 → P2 → P3 (MVP STOP) → P4 → P5 → P6 → P7 → P8
```

P1 与 P2 可并行（不同 service 文件）；P3 依赖 P1+P2。P7 依赖 P3 API 至少 stub 完成。

### Parallel Examples

```bash
# P0 模型
backend/src/models/tender_requirement_context.py
backend/src/models/generation_task.py
backend/src/models/chapter_draft.py
backend/src/models/generation_snapshot.py

# P3 核心服务（P3-1 完成后）
backend/src/services/generation/citation_binder.py
backend/src/services/generation/compliance_checker.py
backend/tests/unit/test_citation_binder.py
```

---

**Plan complete.** bite-sized TDD 步骤见上文；任务 ID 与文件路径详见 `specs/008-generation-assist-upgrade/tasks.md`（T001–T072）。

**Plan complete and saved to `docs/superpowers/plans/2026-06-14-epic6-generation-assist.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 每个 Task 派发全新 subagent，任务间 review，迭代快

**2. Inline Execution** — 本会话用 executing-plans 按 Checkpoint 批量执行（MVP 建议停在 P3）

**Which approach?**
