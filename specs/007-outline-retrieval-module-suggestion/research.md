# Research: Epic 5 目录级检索与模块建议

**Date**: 2026-06-14  
**Feature**: `specs/007-outline-retrieval-module-suggestion`

## R1 — 混合检索管线架构（Multi-Recall Pipeline）

### Decision

实现 **可配置多路召回 + 融合排序 + 规则评分明细** 管线，统一入口 `RetrievalService.search()`：

```text
RetrievalRequest
  → 前置过滤（kb_id、status=published、searchable、product_category、chapter_taxonomy）
  → 按 intent 选择召回策略组合（metadata / keyword / vector / structure）
  → 多路召回合并去重
  → 融合打分 + rule_ranker 生成 score + score_detail
  → 可选 rerank 钩子（策略版本配置 enable_rerank）
  → 组装 Knowledge Pack 扩展字段
  → 写入 retrieval_trace（含策略版本号与中间摘要）
  → 返回 RetrievalResponse
```

目录级匹配（Bid Outline / Template Chapter / Chapter Pattern）走 **structure recall** 子管线，
与内容检索共享 trace 与策略版本框架。

### Rationale

- 对齐总需求 §13 与 Epic 5 spec FR-011–FR-013。
- 单入口便于 trace、反馈、评测绑定同一 trace_id。
- intent 差异化策略通过 `retrieval_strategy_versions.config` 驱动，无需硬编码分支散落。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 每对象类型独立 search API | trace/反馈/评测碎片化；前端调用复杂 |
| 引入 Elasticsearch 专集群 | MVP 运维成本高；PostgreSQL 可满足初版规模 |
| 纯向量检索 | 目录结构匹配与元数据过滤是硬约束，纯向量不足 |

---

## R2 — 关键词与向量存储（PostgreSQL + pgvector）

### Decision

- **关键词召回**：PostgreSQL `tsvector` + GIN 索引，中文采用 `simple` 配置 + 标题/正文
  拼接字段；BM25 权重映射到策略配置中的字段权重（title vs content）。
- **向量召回**：引入 **pgvector** 扩展；`retrieval_index_entries.embedding` 存 `vector(1536)`
  （维度随 embedding 配置版本可变，版本表记录维度）。
- **Docker**：`docker-compose.yml` 中 Postgres 镜像切换为 `pgvector/pgvector:pg15`，
  Alembic migration 执行 `CREATE EXTENSION IF NOT EXISTS vector`。

索引条目表 **多态** 覆盖：ku、wiki、template、template_chapter、bid_outline、
bid_outline_node、chapter_pattern、manual_asset。

### Rationale

- 仓库当前无检索基础设施；PostgreSQL 一体化降低 MVP 复杂度。
- Epic 4 已约定 `searchable=true` 门控；索引构建仅消费正式已发布资产。
- pgvector 与 SQLAlchemy 2.0 生态成熟，满足 Recall@K 评测复现。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 仅 SQL LIKE / ILIKE | 无法支撑语义相似与 SC-003 来源追溯质量 |
| 外挂向量库（Milvus） | 部署与数据同步成本；当前规模不必要 |
| 应用内全表扫描向量 | 无法满足 P95 < 2s（SC-001） |

---

## R3 — Embedding 与索引构建

### Decision

- **Embedding 客户端**：`EmbeddingClient` 抽象，初版通过环境变量配置 OpenAI 兼容
  HTTP API（`EMBEDDING_API_BASE`、`EMBEDDING_MODEL`）；未配置时 **降级为仅关键词+元数据召回**，
  trace 中记录 `vector_disabled_reason`。
- **索引构建**：发布/废弃正式资产时通过 **同步钩子** 更新 `retrieval_index_entries`；
  批量重建通过管理 API `POST /retrieval/index/rebuild`（按 kb_id + object_types）。
- **版本绑定**：每条 index entry 记录 `embedding_config_version`；策略版本变更 embedding
  时触发按需重建任务（`downstream_task_entry` 类型 `retrieval_index_rebuild`）。

### Rationale

- Constitution 不要求固定 LLM 供应商；配置化符合 V3.0 调参闭环。
- 降级路径保证无 embedding 密钥时仍可验收规则评分与结构匹配路径。
- 与 Epic 2/4 publish 事件挂钩，避免候选或未发布资产进入索引。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 每次查询实时 embedding | 延迟不可控；违背 P95 目标 |
| 本地 sentence-transformers | 增加容器体积与 GPU 依赖；MVP 优先 API |

---

## R4 — match_score 与 coverage_rate（可解释规则评分）

### Decision

独立服务 `MatchScoreCalculator`，与检索融合分分离：

| 维度 | 默认权重 | 计算方式 |
|------|----------|----------|
| 产品分类匹配 | 30% | 目标 product_category_ids 与对象分类交集比例 |
| 章节分类覆盖 | 30% | 目标章节映射 taxonomy 与对象 taxonomy 匹配率 |
| 标题语义相似 | 20% | 标准化标题与对象标题的字符/词重叠 + 可选向量余弦 |
| 层级顺序相似 | 10% | 目录节点 level/sort_order 序列编辑距离归一化 |
| 可用知识覆盖 | 10% | 节点下可检索 KU/Wiki/Manual Asset 计数归一化 |

`coverage_rate = matched_target_chapters / total_target_chapters`；缺失章节诊断复用
Chapter Pattern `frequency` 与 `source_outline_ids` 统计。

阈值默认：`frequency >= 3` OR `frequency / category_outline_count >= 0.30`，
存于 `retrieval_strategy_versions.config.gap_threshold`。

### Rationale

- Epic 5 与总需求明确「增强阶段先采用可解释规则评分」。
- score_detail JSON 逐项记录子分数，满足管理后台与验收展示。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 单一 retrieval score | 无法解释目录匹配与内容检索差异 |
| ML 学习排序 | Out of Scope；策略版本机制预留扩展 |

---

## R5 — 模块组织建议编排（Module Suggestion Orchestrator）

### Decision

`ModuleSuggestionService.suggest()` 编排：

```text
TenderRequirementContext + outline_nodes + product_category_ids
  → 章节标题标准化 + taxonomy 映射
  → 对每个 target_outline_node 并行：
      structure recall（Template Chapter / Bid Outline Node / Chapter Pattern）
      knowledge recall（KU / Wiki / Manual Asset）
      MatchScoreCalculator + coverage
      ScorePointCoverageAnalyzer（评分点文本与推荐对象标题/摘要匹配）
      RejectionRiskDetector（废标项与推荐内容冲突检测）
      TemplateConflictDetector（模板章节 vs 招标结构/评分点/废标项）
  → 聚合 module_suggestions + 持久化 module_assembly_suggestions 行（供 Epic 6）
  → 返回 trace_id
```

**招标优先原则**：`TemplateConflictDetector` 命中时设置 `risk_flags`，
`suggested_template_chapter_ids` 不包含冲突项（FR-010）。

### Rationale

- 模块建议是无 LLM 编排（SC-001 P95 < 2s）；与 Epic 6 草稿生成解耦。
- 持久化 suggestion 供下游消费与审计，trace_id 双向关联。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 仅返回即时 JSON 不持久化 | Epic 6 与审计需要稳定 suggestion_id |
| LLM 生成组织建议 | 超出 Epic 5 范围；延迟超标 |

---

## R6 — retrieval_trace 与反馈/评测数据模型

### Decision

- **retrieval_traces**：主表存 request_snapshot、strategy_version_id、intent、
  response_summary、latency_ms、status；大字段 `stages` JSONB 存召回/排序中间摘要。
- **retrieval_feedbacks**：trace_id + result_object_type/id + feedback_type enum +
  optional expected_object_ids（漏召回）。
- **retrieval_eval_sets / retrieval_eval_cases**：评测集与用例；`created_from` 枚举
  manual | user_feedback | production_log；反馈转用例需 `confirmed_at` + `confirmed_by`。
- **retrieval_strategy_versions**：name、version_tag、config JSONB（召回开关、权重、
  top_k、gap_threshold、embedding_version、rerank_version、prompt_version）。

评测执行：`RetrievalEvalRunner` 对评测集批量调用 `RetrievalService`，输出 metrics JSON
（Recall@K、Precision@K、MRR、NDCG、采纳率、误/漏召回率、有来源占比）；支持两版本对比 API。

### Rationale

- 满足 FR-013–FR-018 与 SC-002、SC-004、SC-007。
- JSONB stages 避免过度规范化；trace 查询以管理后台为主。

### Alternatives considered

| 方案 | 放弃原因 |
|------|----------|
| 仅应用日志无结构化表 | 无法支撑评测复现与反馈关联 |
| 每条召回一行明细表 | MVP 写入量大；JSON 摘要足够运营排查 |

---

## R7 — Knowledge Pack 扩展与下游契约

### Decision

检索结果项统一 `KnowledgePackItem` Pydantic 模型，在现有 KU/Wiki 等字段上扩展：

```json
{
  "product_category": [],
  "chapter_taxonomy": {},
  "template_chapter_hints": [],
  "bid_outline_context": [],
  "chapter_patterns": [],
  "candidate_source": {},
  "import_id": "",
  "score_detail": {},
  "hit_reason": ""
}
```

`hit_reason` 为人类可读一句；`score_detail` 为结构化子分。模块建议 API 内嵌
`KnowledgePackItem` 列表字段。

### Rationale

- 对齐总需求 §13.4 与 spec FR-014；Epic 6 单契约消费。

---

## R8 — 管理后台 UI 划分

### Decision

- **目录中心（OutlineCenter 扩展）**：已有 Bid Outline 列表/树编辑；Epic 5 新增
  「目录相似度」侧栏/抽屉，调用 directory match API 展示 match_score、coverage_rate、
  score_detail；Chapter Pattern 确认沿用现有或轻量扩展。
- **检索优化中心（RetrievalOptimizationCenter 新页）**：trace 列表/详情、反馈汇总、
  评测集 CRUD、策略版本管理与对比、策略配置表单（召回开关、权重、top_k）。
- **模块建议入口**：OutlineDetailPage 或独立「模块建议」向导，提交招标约束上下文。

路由：`/retrieval-optimization`；菜单与 Epic 4 CandidateCenter 同级。

### Rationale

- 对齐总需求 §15.4、§15.7；复用 OutlineCenter 减少重复 Bid Outline CRUD。

---

## R9 — 测试策略

### Decision

- **契约测试**：retrieval search、module suggestion、feedback、eval compare API。
- **集成测试**：seed 已发布 KU + Bid Outline + Chapter Pattern → 检索 → 反馈 →
  trace 可查；产品分类过滤负向用例；模板冲突 risk_flags。
- **性能测试**：模块建议路径 P95 < 2s（pytest benchmark 或 locust 轻量，典型 KB 规模
  fixtures：~200 索引条目、~20 outline）。
- **评测指标单元测试**：metrics 计算纯函数覆盖 Recall@K、NDCG。

### Rationale

- Constitution TDD；SC-001/SC-005/SC-006 需可自动化验证。
