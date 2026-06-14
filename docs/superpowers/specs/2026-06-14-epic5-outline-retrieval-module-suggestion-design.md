# Design: Epic 5 目录级检索与模块建议

**Date**: 2026-06-14  
**Status**: Approved  
**Feature spec**: `specs/007-outline-retrieval-module-suggestion/spec.md`  
**Implementation plan (Spec Kit)**: `specs/007-outline-retrieval-module-suggestion/plan.md`  
**Spec Kit tasks**: `specs/007-outline-retrieval-module-suggestion/tasks.md` (T001–T078)  
**Epic source**: `docs/epics/epic5-目录级检索与模块建议.md`

## 1. 背景与目标

Epic 0–4 已产出 **已发布** 知识资产（KU/Wiki/Manual Asset、Bid Outline、Template Chapter、
Chapter Pattern）及 `searchable` 门控。Epic 5 交付 V3.0-增强阶段 **检索优先** 能力：

- 目录级检索与可解释 `match_score` / `coverage_rate`
- 缺失章节诊断（Chapter Pattern 频次阈值）
- **无 LLM** 模块组织建议（外部招标约束优先于模板库）
- `retrieval_trace` 全链路追溯
- 检索反馈、评测集、策略版本对比闭环
- Knowledge Pack 扩展字段供 Epic 6 消费

本设计在 Spec Kit 制品基础上，补充 brainstorming 决议的 **全量交付 D、Embedding 可降级、
模块建议 Wizard、检索优化中心 Tabs、P0–P4 切片**。

## 2. Brainstorming 决议摘要

| # | 议题 | 决议 |
|---|------|------|
| D1 | 交付范围 | **全量 D**：T001–T078（API + OutlineCenter + RetrievalOptimizationCenter） |
| D2 | Embedding | **可降级**：未配置 API 时 tsvector + 元数据 + 结构匹配；trace 记 `vector_disabled_reason` |
| D3 | 模块建议 UI | **分步 Wizard**：选上下文 → 招标约束 → 结果预览 |
| D4 | 检索优化中心 | **单页 Tabs**：Trace / 反馈 / 评测集 / 策略版本 |
| D5 | Spec Kit 对齐 | 不扩 scope；UX 与实现切片补充 |

## 3. 实现路径对比（Brainstorming）

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| ① 后端先行 | API 全部完成后再 UI | 契约稳定 | 全量 D 下验收滞后 |
| ② 按 US 竖切全栈 | 每故事前后端一起 | 故事独立 | 同文件冲突多 |
| **③ 分层竖切（采用）** | P0 基建 → P1 目录+建议 → P2 统一检索 → P3 反馈评测 → P4 UI+polish | 与 tasks.md 一致；早验收 P1 | 需 P0 阻塞 |

## 4. 架构

### 4.1 前后端边界

```text
┌─────────────────────────────────────────────────────────────────┐
│ OutlineCenter                                                   │
│  ├─ 现有：列表 / OutlineTreeEditor / Diff                       │
│  ├─ OutlineSimilarityDrawer：directory-match                      │
│  └─ ModuleSuggestionWizard：3 步 → POST module-suggestions    │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│ RetrievalOptimizationCenter (/retrieval-optimization)           │
│  Tabs: [ Trace ] [ 反馈 ] [ 评测集 ] [ 策略版本 ]                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ API Layer                                                       │
│  POST /retrieval/search | /directory-match | GET /traces/*      │
│  POST /module-suggestions | GET /module-suggestions/{id}        │
│  POST /retrieval/feedback | /eval/* | /strategies/*             │
│  POST /retrieval/index/rebuild                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ services/retrieval/                                             │
│  retrieval_pipeline                                             │
│    ├─ recall: metadata | keyword(tsvector) | vector(pgvector)   │
│    ├─ recall: structure (outline/template/pattern)              │
│    ├─ ranking: fusion_ranker | conflict_detector                  │
│    ├─ match_score_calculator | chapter_gap_diagnoser              │
│    ├─ module_suggestion_service                                 │
│    ├─ indexing: index_builder + embedding_client (degradable)   │
│    ├─ trace: retrieval_trace_service                            │
│    ├─ feedback: retrieval_feedback_service                      │
│    └─ eval: eval_runner + metrics                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ PostgreSQL 15 + pgvector                                        │
│  retrieval_index_entries | retrieval_traces                       │
│  module_assembly_suggestions | retrieval_feedbacks                │
│  retrieval_eval_* | retrieval_strategy_versions                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 索引同步

| 源事件 | 动作 |
|--------|------|
| Epic 4 publish KU/Wiki/Manual Asset/Template Chapter | UPSERT `retrieval_index_entries` |
| Bid Outline / Node 发布 | UPSERT |
| Chapter Pattern confirmed | UPSERT |
| 资产 deprecated / searchable=false | status=deprecated 或排除召回 |
| 管理员 | `POST /retrieval/index/rebuild` |

**硬规则**：未确认 Candidate Knowledge **永不**进入索引。

### 4.3 match_score 默认权重

| 维度 | 权重 |
|------|------|
| 产品分类匹配 | 30% |
| 章节分类覆盖 | 30% |
| 标题语义相似 | 20% |
| 层级顺序相似 | 10% |
| 可用知识覆盖 | 10% |

`coverage_rate = 已匹配目标章节数 / 目标章节总数`

缺失章节：`frequency >= 3` OR `frequency / category_outline_count >= 0.30`（策略可配置）

### 4.4 招标优先与冲突

`conflict_detector` 比对招标结构/评分点/废标项与模板章节建议：

- 命中冲突 → `risk_flags` + `rejection_risks`
- **MUST NOT** 将冲突 `template_chapter_id` 写入 `suggested_template_chapter_ids`

## 5. UI 设计

### 5.1 目录相似度 `OutlineSimilarityDrawer`

- **入口**：`OutlineDetailPage` 工具栏「目录相似度」
- **调用**：`POST /retrieval/directory-match`（当前 outline 节点 + `product_category_ids`）
- **展示**：`match_score`、`coverage_rate`、`score_detail`（Collapse）；相似 Outline/Pattern 列表；`missing_chapters` Alert 列表

### 5.2 模块建议 `ModuleSuggestionWizard`（D3）

```text
Step 1  上下文
  - 产品分类 TreeSelect、项目类型、客户类型
  - 目标节点多选（默认当前 Bid Outline 树勾选）

Step 2  招标约束
  - score_points Form.List
  - rejection_clauses Form.List
  - format_requirements（可选）

Step 3  结果
  - 按 target_outline_node 卡片：match_score、coverage、推荐 ID 摘要
  - risk_flags 红 Tag；缺失章节列表
  - trace_id + 链接「在检索优化中心查看」
```

- **入口**：Outline 详情「生成模块建议」→ Modal 全屏 Wizard
- **API**：`POST /module-suggestions`

### 5.3 检索优化中心 Tabs（D4）

| Tab | 组件 | 能力 |
|-----|------|------|
| Trace | `index.tsx` + `TraceDetailDrawer` | 列表筛选；详情 request/stages/response |
| 反馈 | `FeedbackPanel` | 按 trace 查；提交 useful/false_positive/false_negative |
| 评测集 | `EvalSetPanel` | Set/Case CRUD；反馈晋升；confirm 门禁 |
| 策略版本 | `StrategyVersionPanel` | 配置编辑；activate；触发 eval run 对比 |

路由：`/retrieval-optimization`；菜单与 CandidateCenter 同级。

### 5.4 API Client

| 文件 | 职责 |
|------|------|
| `frontend/src/services/retrieval.ts` | search, directory-match, traces, index/rebuild |
| `frontend/src/services/moduleSuggestions.ts` | module-suggestions CRUD |
| `frontend/src/services/retrievalEval.ts` | feedback, eval, strategies |

## 6. 交付切片 P0–P4

```text
P0  基建 (T001–T022)
  pgvector 镜像、migration、8 ORM、schemas、trace/index/embedding、
  publish 索引钩子、策略 seed、title_normalizer 单测

P1  目录 + 模块建议 (T023–T040)
  structure_recall、match_score、gap、module_suggestion、conflict_detector
  OutlineSimilarityDrawer + ModuleSuggestionWizard
  验收：quickstart 场景 2–3

P2  统一检索 (T041–T051)
  metadata/keyword/vector recall、fusion、POST /search、traces、rebuild
  验收：场景 1、4、7

P3  反馈 + 评测 API (T052–T062)
  feedback、eval sets/cases/runs、strategy activate
  验收：场景 5–6

P4  后台 UI 补齐 + polish (T063–T078)
  RetrievalOptimizationCenter 四 Tab、integration、P95 探针、quickstart 全绿
```

**全量 D 验收线**：P4 完成 = spec 7 用户故事 + SC-001–SC-007 可测。

## 7. Embedding 降级（D2）

| 条件 | 行为 |
|------|------|
| `EMBEDDING_API_BASE` 未配置 | `vector_recall` 跳过；`stages.vector_disabled_reason` |
| 已配置 | 正常 embedding + pgvector 余弦召回 |
| 索引 | `embedding` 列 nullable；无 API 时仅维护 tsvector |

不得伪造向量分；UI/API 响应中可选展示 `vector_enabled: false`。

## 8. 数据与迁移要点

详见 `specs/007-outline-retrieval-module-suggestion/data-model.md`。强调：

- `retrieval_index_entries` UNIQUE `(kb_id, object_type, object_id)`
- `module_assembly_suggestions` 持久化供 Epic 6；关联 `trace_id`
- `retrieval_eval_cases`：`created_from=user_feedback` 须 `confirmed_at` 方可参与评测
- 每 kb 仅一个 `is_active=true` 策略版本

## 9. 错误处理

| 场景 | 行为 |
|------|------|
| 无 Embedding | 降级召回；trace 记录原因 |
| outline_nodes 为空 | 422 `EMPTY_OUTLINE` |
| 零检索结果 | 200 + 空列表 + 放宽过滤提示 |
| 模板/招标冲突 | `risk_flags` 非空；不推荐冲突模板 |
| 漏召回反馈无期望 | 422 |
| 评测集无 confirmed 用例 | 422 `EVAL_SET_EMPTY` |
| pending 候选 | 永不索引；契约负向测试 |

## 10. 测试策略

| 层级 | 范围 |
|------|------|
| unit | `match_score_calculator`、`chapter_gap_diagnoser`、`eval/metrics`、title_normalizer |
| contract | retrieval search/directory-match/traces、module-suggestion、feedback、eval |
| integration | `test_epic5_quickstart_flow`、候选隔离、模板冲突 risk_flags |
| performance | 模块建议 P95 < 2s（`test_module_suggestion_performance`） |
| e2e manual | quickstart 场景 0–7 |

## 11. 与 Spec Kit 制品关系

| 制品 | 本设计增量 |
|------|------------|
| spec.md | 无范围变更；UX/切片补充 |
| plan.md | 文件路径与 P0–P4 对齐 §6 |
| research.md | R8 UI 细化为 §5；D2 细化为 §7 |
| tasks.md | T001–T078 与 §6 一一对应 |
| contracts/* | 与 §4 API 一致 |

## 12. 明确不做

- 章节草稿生成（Epic 6）
- Template Instance 完整实例化
- 招标文件完整解析系统
- 复杂自动学习系统
- 无配置时假装向量召回成功

## 13. 下一步

1. Superpowers 实现计划：`docs/superpowers/plans/2026-06-14-epic5-outline-retrieval-module-suggestion.md`  
2. Superpowers TDD 按 P0→P4 执行 `tasks.md`  
3. quickstart 全绿后合并

---

**Decision log (brainstorming)**

- 2026-06-14 D1: 全量交付 D (T001–T078)
- 2026-06-14 D2: Embedding 可降级 B
- 2026-06-14 D3: 模块建议分步 Wizard B
- 2026-06-14 D4: 检索优化中心单页 Tabs A
- 2026-06-14 Delivery: 分层竖切 P0–P4 (方案 ③)
