# Epic 5 目录级检索与模块建议 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付目录级检索、缺失章节诊断、无 LLM 模块组织建议、统一混合检索、`retrieval_trace`、反馈与评测闭环、策略版本管理；扩展 OutlineCenter + RetrievalOptimizationCenter 全量 UI。

**Architecture:** PostgreSQL 15 + pgvector；统一 `retrieval_index_entries` 多态索引；`services/retrieval/` 多路召回管线（metadata / tsvector / vector 可降级 / structure）；`match_score_calculator` 规则评分；`module_suggestion_service` 招标优先编排；纵向切片 P0→P4 对齐 `tasks.md` T001–T078。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL + pgvector | React 18, Ant Design 5, Vite | pytest, httpx

**Design doc:** `docs/superpowers/specs/2026-06-14-epic5-outline-retrieval-module-suggestion-design.md`  
**Feature spec:** `specs/007-outline-retrieval-module-suggestion/spec.md`  
**Spec Kit tasks:** `specs/007-outline-retrieval-module-suggestion/tasks.md` (T001–T078)  
**Data model:** `specs/007-outline-retrieval-module-suggestion/data-model.md`  
**Contracts:** `specs/007-outline-retrieval-module-suggestion/contracts/`

---

## File Map

| 路径 | 职责 |
|------|------|
| `docker-compose.yml` | Postgres → `pgvector/pgvector:pg15` |
| `backend/alembic/versions/*_epic5_retrieval.py` | vector 扩展 + 8 表 |
| `backend/src/models/retrieval_*.py` | 检索 ORM（8 实体） |
| `backend/src/models/module_assembly_suggestion.py` | 模块建议持久化 |
| `backend/src/schemas/retrieval.py` | RetrievalRequest、KnowledgePackItem |
| `backend/src/services/retrieval/retrieval_service.py` | search / directory-match 入口 |
| `backend/src/services/retrieval/retrieval_pipeline.py` | 多路召回编排 |
| `backend/src/services/retrieval/recall/*.py` | metadata / keyword / vector / structure |
| `backend/src/services/retrieval/ranking/*.py` | fusion_ranker、conflict_detector |
| `backend/src/services/retrieval/match_score_calculator.py` | 五维规则分 |
| `backend/src/services/retrieval/chapter_gap_diagnoser.py` | 缺失章节 |
| `backend/src/services/retrieval/module_suggestion/module_suggestion_service.py` | 模块建议编排 |
| `backend/src/services/retrieval/indexing/*.py` | index_builder、embedding_client |
| `backend/src/services/retrieval/trace/retrieval_trace_service.py` | trace 读写 |
| `backend/src/services/retrieval/feedback/*.py` | 反馈 |
| `backend/src/services/retrieval/eval/*.py` | metrics、eval_runner |
| `backend/src/api/routes/retrieval.py` | search、directory-match、traces、rebuild |
| `backend/src/api/routes/module_suggestions.py` | module-suggestions |
| `backend/src/api/routes/retrieval_feedback.py` | feedback |
| `backend/src/api/routes/retrieval_eval.py` | eval + strategies |
| `backend/src/services/publishers/ku_publisher.py` | 挂接 index_builder |
| `frontend/src/pages/OutlineCenter/OutlineSimilarityDrawer.tsx` | 目录相似度 |
| `frontend/src/pages/OutlineCenter/ModuleSuggestionWizard.tsx` | 3 步 Wizard |
| `frontend/src/pages/RetrievalOptimizationCenter/*.tsx` | 四 Tab 后台 |
| `frontend/src/services/retrieval.ts` | API client |
| `backend/tests/integration/test_epic5_quickstart_flow.py` | quickstart 集成 |

---

## Phase P0 — 基建（T001–T022，阻塞）

### Task P0-1: pgvector 与 Docker（T001）

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1:** 将 `postgres` 镜像改为 `pgvector/pgvector:pg15`，保留现有 env/volume。

- [ ] **Step 2:** 重启数据库并验证扩展：

```bash
docker compose up -d postgres
docker compose exec postgres psql -U tender -d tender_knowledge -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Expected: `CREATE EXTENSION`

### Task P0-2: Migration + ORM 注册（T005–T014）

**Files:**
- Create: `backend/alembic/versions/*_epic5_retrieval.py`
- Create: `backend/src/models/retrieval_index_entry.py`（等 8 模型）
- Modify: `backend/src/models/__init__.py`
- Modify: `backend/src/db/init_db.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_epic5_models.py`

- [ ] **Step 1: 写模型集成测试**

```python
# backend/tests/integration/test_epic5_models.py
from uuid import uuid4

from src.models.retrieval_trace import RetrievalTrace, RetrievalTraceStatus


def test_create_retrieval_trace(db_session):
    trace = RetrievalTrace(
        kb_id=uuid4(),
        intent="knowledge_lookup",
        strategy_version_id=uuid4(),
        request_snapshot={"query": "技术方案"},
        status=RetrievalTraceStatus.success,
        latency_ms=100,
    )
    db_session.add(trace)
    db_session.commit()
    assert trace.trace_id is not None
```

- [ ] **Step 2:** 按 `data-model.md` 实现 8 个 ORM + Alembic（含 `CREATE EXTENSION vector`、`retrieval_index_entries.embedding vector(1536)`、GIN on tsvector）。

- [ ] **Step 3:** 注册到 `init_db.py` / `conftest.py`，跑测试：

```bash
cd backend && ../.venv/bin/pytest tests/integration/test_epic5_models.py -v
```

Expected: PASS

### Task P0-3: Schemas + title_normalizer（T015, T017, T022）

**Files:**
- Create: `backend/src/schemas/retrieval.py`
- Create: `backend/src/services/retrieval/title_normalizer.py`
- Create: `backend/tests/unit/test_title_normalizer.py`

- [ ] **Step 1: 失败单测**

```python
# backend/tests/unit/test_title_normalizer.py
from src.services.retrieval.title_normalizer import normalize_outline_title

def test_normalize_strips_numbering():
    assert normalize_outline_title("1.2 技术方案") == "技术方案"
```

- [ ] **Step 2:** 实现 `normalize_outline_title`（去编号、空白、全半角）。

- [ ] **Step 3:** 定义 `RetrievalRequest`、`RetrievalIntent` enum、`KnowledgePackItem` Pydantic 模型。

### Task P0-4: Embedding + IndexBuilder + 策略 seed（T018–T021）

**Files:**
- Create: `backend/src/services/retrieval/indexing/embedding_client.py`
- Create: `backend/src/services/retrieval/indexing/index_builder.py`
- Create: `backend/src/services/retrieval/strategy_seed.py`
- Modify: `backend/src/services/publishers/ku_publisher.py`（及 wiki/manual_asset/template_chapter publisher）

- [ ] **Step 1:** `EmbeddingClient.embed(texts)` — 读 `EMBEDDING_API_BASE`/`EMBEDDING_API_KEY`；未配置时 `is_configured=False`。

- [ ] **Step 2:** `IndexBuilder.upsert_from_ku(ku)` — 写 `retrieval_index_entries`（title、content_text、tsvector、embedding 可选）。

- [ ] **Step 3:** `seed_default_strategy(db, kb_id)` — 插入 `retrieval_strategy_versions` config（见 research.md）。

- [ ] **Step 4:** KU publish 成功后调用 `index_builder.upsert_from_ku`。

### Task P0-5: 路由壳（T002–T004）

**Files:**
- Modify: `backend/src/main.py`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/RetrievalOptimizationCenter/index.tsx`（空壳 Tabs）

- [ ] 注册 4 个 API router；前端 `/retrieval-optimization` 路由 + 菜单。

**Checkpoint P0:** migration 成功；发布 KU 触发索引；默认策略存在。

---

## Phase P1 — 目录匹配 + 模块建议（T023–T040）

### Task P1-1: match_score + structure_recall（T023–T028）

**Files:**
- Create: `backend/src/services/retrieval/match_score_calculator.py`
- Create: `backend/src/services/retrieval/recall/structure_recall.py`
- Create: `backend/tests/unit/test_match_score_calculator.py`
- Create: `backend/tests/contract/test_retrieval_directory_match.py`

- [ ] **Step 1: match_score 单测**

```python
def test_product_category_weight_30_percent():
    from src.services.retrieval.match_score_calculator import MatchScoreCalculator
    calc = MatchScoreCalculator(weights={"product_category": 0.3, ...})
    detail = calc.compute(
        target_product_category_ids=["a"],
        object_product_category_ids=["a"],
        ...
    )
    assert detail["product_category"] == 0.3
```

- [ ] **Step 2:** 实现 `structure_recall` 查询 Bid Outline / Template Chapter / Chapter Pattern。

- [ ] **Step 3:** 契约测试 `POST /directory-match` 返回 `match_score`、`coverage_rate`、`score_detail`。

### Task P1-2: chapter_gap（T031–T034）

**Files:**
- Create: `backend/src/services/retrieval/chapter_gap_diagnoser.py`
- Create: `backend/tests/unit/test_chapter_gap_diagnoser.py`

- [ ] 实现频次阈值逻辑；并入 directory-match 响应 `missing_chapters`。

### Task P1-3: module_suggestion + conflict（T035–T040）

**Files:**
- Create: `backend/src/services/retrieval/ranking/conflict_detector.py`
- Create: `backend/src/services/retrieval/module_suggestion/module_suggestion_service.py`
- Create: `backend/src/api/routes/module_suggestions.py`
- Create: `backend/tests/contract/test_module_suggestion.py`
- Create: `backend/tests/integration/test_module_suggestion_conflict.py`

- [ ] **Step 1:** `conflict_detector` — 招标评分点/废标项 vs 模板标题 → `risk_flags`。

- [ ] **Step 2:** `module_suggestion_service.suggest()` — 按 outline_node 编排；持久化 `module_assembly_suggestions`；**冲突模板 ID 不写入** `suggested_template_chapter_ids`。

- [ ] **Step 3:** 契约测试 + 冲突场景 integration test。

### Task P1-4: OutlineCenter UI（T066–T068 部分，Wizard + Drawer）

**Files:**
- Create: `frontend/src/pages/OutlineCenter/OutlineSimilarityDrawer.tsx`
- Create: `frontend/src/pages/OutlineCenter/ModuleSuggestionWizard.tsx`
- Modify: `frontend/src/pages/OutlineCenter/OutlineDetailPage.tsx`
- Create: `frontend/src/services/retrieval.ts`
- Create: `frontend/src/services/moduleSuggestions.ts`

- [ ] Wizard 三步（设计 §5.2）；SimilarityDrawer 调 directory-match。

**Checkpoint P1:** quickstart 场景 2–3 通过。

---

## Phase P2 — 统一检索（T041–T051）

### Task P2-1: 多路召回管线

**Files:**
- Create: `backend/src/services/retrieval/recall/metadata_recall.py`
- Create: `backend/src/services/retrieval/recall/keyword_recall.py`
- Create: `backend/src/services/retrieval/recall/vector_recall.py`
- Create: `backend/src/services/retrieval/ranking/fusion_ranker.py`
- Create: `backend/src/services/retrieval/retrieval_pipeline.py`
- Modify: `backend/src/services/retrieval/retrieval_service.py`
- Create: `backend/tests/contract/test_retrieval_search.py`
- Create: `backend/tests/integration/test_retrieval_isolation.py`

- [ ] **Step 1:** keyword_recall 使用 `ts_rank` + GIN。

- [ ] **Step 2:** vector_recall — `EmbeddingClient.is_configured` 为 false 时跳过并返回 `vector_disabled_reason`。

- [ ] **Step 3:** `POST /retrieval/search` + `GET /traces/*` + `POST /index/rebuild`。

- [ ] **Step 4:** 负向测试 pending 候选不在 search 结果。

**Checkpoint P2:** quickstart 场景 1、4、7。

---

## Phase P3 — 反馈 + 评测 API（T052–T062）

### Task P3-1: Feedback

**Files:**
- Create: `backend/src/services/retrieval/feedback/retrieval_feedback_service.py`
- Create: `backend/src/api/routes/retrieval_feedback.py`
- Create: `backend/tests/contract/test_retrieval_feedback.py`

- [ ] POST feedback 绑定 trace_id；`false_negative` 无期望 → 422；promote-to-eval-case → pending case。

### Task P3-2: Eval + Strategy

**Files:**
- Create: `backend/src/services/retrieval/eval/metrics.py`
- Create: `backend/src/services/retrieval/eval/eval_runner.py`
- Create: `backend/src/api/routes/retrieval_eval.py`
- Create: `backend/tests/unit/test_eval_metrics.py`
- Create: `backend/tests/contract/test_retrieval_eval.py`

- [ ] **Step 1:** `recall_at_k`、`ndcg` 纯函数单测。

- [ ] **Step 2:** eval case confirm 门禁；双策略 `comparison_metrics`；strategy activate 互斥 `is_active`。

**Checkpoint P3:** quickstart 场景 5–6。

---

## Phase P4 — RetrievalOptimizationCenter + Polish（T063–T078）

### Task P4-1: 检索优化中心四 Tab（T069–T073）

**Files:**
- Modify: `frontend/src/pages/RetrievalOptimizationCenter/index.tsx`
- Create: `TraceDetailDrawer.tsx`、`EvalSetPanel.tsx`、`StrategyVersionPanel.tsx`、`FeedbackPanel.tsx`
- Create: `frontend/src/services/retrievalEval.ts`

- [ ] 四 Tab 对齐设计 §5.3；Trace 列表 + 详情 stages；策略对比触发 eval run。

### Task P4-2: 集成 + 性能 + quickstart（T074–T078）

**Files:**
- Create: `backend/tests/integration/test_epic5_quickstart_flow.py`
- Create: `backend/tests/integration/test_module_suggestion_performance.py`

- [ ] **Step 1:** 集成测试覆盖：directory-match → module-suggestion → feedback → trace 查询。

- [ ] **Step 2:** 模块建议 P95 < 2s（典型 fixture ~200 索引条目）。

- [ ] **Step 3:** 跑 `specs/007-outline-retrieval-module-suggestion/quickstart.md` 场景 0–7 并修缺口。

```bash
cd backend && ../.venv/bin/pytest tests/ -v -k "retrieval or module_suggestion or eval"
```

**Checkpoint P4（全量 D）:** spec 7 用户故事 + SC-001–SC-007 可测。

---

## Spec Coverage Checklist

| Spec 要求 | 任务 |
|-----------|------|
| FR-001–FR-006 目录检索/评分/缺失 | P1-1, P1-2 |
| FR-007–FR-010 模块建议/招标优先 | P1-3 |
| FR-011–FR-013 参数化检索/trace | P2-1, P0-4 trace service |
| FR-014 Knowledge Pack | P1-1 knowledge_pack_builder |
| FR-015–FR-018 反馈/评测 | P3 |
| FR-019–FR-020 管理后台 | P1-4, P4-1 |
| FR-021–FR-022 API + 候选隔离 | P1-3, P2-1 |
| SC-001 P95 < 2s | P4-2 performance test |

---

## Execution Order

```text
P0 → P1 → P2 → P3 → P4
```

P1 与 P2 后端可部分并行（不同子目录），但 `retrieval_service.py` 合并前需协调。

---

## Parallel Examples

```bash
# P0 模型并行
backend/src/models/retrieval_index_entry.py
backend/src/models/retrieval_trace.py
# ... 其余 6 个

# P2 recall 并行
backend/src/services/retrieval/recall/metadata_recall.py
backend/src/services/retrieval/recall/keyword_recall.py
backend/src/services/retrieval/recall/vector_recall.py

# P4 UI Panel 并行
frontend/src/pages/RetrievalOptimizationCenter/EvalSetPanel.tsx
frontend/src/pages/RetrievalOptimizationCenter/StrategyVersionPanel.tsx
```

---

**Plan complete.** 详细任务 ID 与文件路径见 `specs/007-outline-retrieval-module-suggestion/tasks.md`（T001–T078）；本计划按 P0–P4 提供 TDD 步骤与验收停点。
