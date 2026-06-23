# Design: 目录蓝图语义检索（Blueprint Semantic Search）

**Date**: 2026-06-22  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-21-directory-blueprint-design.md` · `docs/superpowers/specs/2026-06-22-blueprint-outline-suggest-design.md` · `backend/src/services/knowledge/embedding_task.py`

---

## 1. 背景与目标

### 1.1 痛点

| 痛点 | 说明 |
|------|------|
| 列表检索能力弱 | 现有蓝图列表仅支持 `ILIKE` 关键词 + 标签精确过滤，无法理解语义相近的表达 |
| 蓝图资产难发现 | 用户用自然语言描述需求时，难以快速找到结构/场景相近的目录蓝图 |
| V1 刻意未做检索 | 原蓝图设计将「向量检索集成」标为不在范围；现蓝图数据已积累，需补齐检索能力 |

### 1.2 产品定位

为**目录蓝图列表页**提供语义搜索能力：用户以自然语言描述需求，经 LLM 拆分为向量查询、关键词与标量过滤参数，再通过可配置权重的混合检索返回 Top N 蓝图，并在列表中展示匹配分与高亮摘要。

### 1.3 建设目标

1. **向量索引**：蓝图创建/更新时异步构建 embedding；删除与文档 purge 时级联清理；支持全量重建。
2. **查询接口**：关键词 + 向量 + 标量过滤混合检索；权重由请求参数配置；结果含分数明细与高亮片段。
3. **列表页入口**：独立语义搜索区；LLM 解析 → 混合检索 → 覆盖 Table 展示结果；可「返回列表」恢复普通过滤。

### 1.4 已锁定决策（brainstorming）

| 议题 | 决议 |
|------|------|
| 索引粒度 | A. 蓝图级：每个蓝图 1 条向量 |
| 权重配置 | A. 请求参数（`vector_weight` / `keyword_weight`），前端 V1 使用固定默认值 |
| LLM 解析输出 | A. 拆分：`semantic_query`（向量）+ `keyword`（关键词）+ 标量标签过滤 |
| 索引构建时机 | A. 异步后台；支持删除级联与 `index/rebuild` 全量重建 |
| 结果展示 | A. 覆盖当前 Table（Top N + 分数 + 高亮）；「返回列表」恢复普通过滤 |
| 实现方案 | ① 独立 `blueprint_embeddings` 表 + 混合检索服务（推荐，与 `chunk_embeddings` 模式一致） |

### 1.5 不在范围（V1）

- 节点级向量索引与命中章节展示
- 权重调节 UI（高级面板）
- 语义搜索历史记录
- LLM 解析参数可编辑预览
- 复用 Epic5 全库 `retrieval_index_entries` 多态框架
- E2E 自动化测试

---

## 2. 方案对比与决议

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **① 独立 embedding 表 + 混合检索服务（推荐）** | `blueprint_embeddings` + `EmbeddingClient`；独立 search / parse service | 与 `chunk_embeddings` 一致；边界清晰；删除/重建简单 | 新建 2～3 个 service + migration |
| ② embedding 列挂主表 | `knowledge_blueprints` 增 `embedding` 等字段 | 少一张表 | 主表膨胀；与现有 chunk 模式不一致 |
| ③ 复用 Epic5 多态索引 | `object_type=blueprint` 写入统一检索表 | 未来可统一全库检索 | Epic5 表已清理、无实现；Scope 过重 |

**决议：方案 ①**

---

## 3. 架构与数据模型

### 3.1 总体架构

```text
BlueprintListPage
  ├─ 普通过滤 → GET /blueprints（现有 ILIKE + 标签）
  └─ 语义搜索
       ① POST /blueprints/parse-search-query  → LLM 拆分参数
       ② POST /blueprints/search              → 混合检索 + 排序 + 高亮
       ③ 覆盖 Table 展示 Top N；「返回列表」恢复普通过滤

blueprint_service (create/update/delete)
  └─ BackgroundTasks → blueprint_embedding_task

file_import_purge_service
  └─ 蓝图删除时 FK CASCADE 清理 blueprint_embeddings
```

### 3.2 新表 `blueprint_embeddings`

| 字段 | 类型 | 说明 |
|------|------|------|
| `blueprint_id` | UUID PK, FK | 关联 `knowledge_blueprints`，`ON DELETE CASCADE` |
| `kb_id` | UUID | 冗余，便于按知识库重建 |
| `search_text` | TEXT | 索引原文（关键词匹配与高亮源） |
| `embedding` | vector(1024) | 与 `chunk_embeddings` 维度一致 |
| `embedding_status` | varchar(20) | `pending` / `ready` / `failed` / `skipped` |
| `content_hash` | varchar(64) | 内容变更检测，避免重复 embedding |
| `indexed_at` | timestamptz | 最近索引时间 |

**索引**：`kb_id`；`embedding` 上 HNSW/IVFFlat（与 `chunk_embeddings` 一致）。

### 3.3 `search_text` 拼接规则

蓝图级单条文本，字段以换行拼接：

```text
name
description
product_tags（JSON 数组展平为空格分隔）
industry_tags
scenario_tags
applicable_project_type
suggested_structure_md
各节点（按 node_order 深度优先）:
  node_title + content_description + tender_response_hint
```

### 3.4 索引生命周期

| 事件 | 行为 |
|------|------|
| 创建/更新蓝图 | `BackgroundTasks` 触发 `embed_blueprint(blueprint_id)`：计算 `content_hash` → 变更则重新 embedding → 更新 `embedding_status` |
| 删除蓝图 | FK `ON DELETE CASCADE` 删除 embedding 行 |
| 文档 purge | 随 `knowledge_blueprints` 级联删除（扩展 purge 计数日志） |
| 手动重建 | `POST /kbs/{kb_id}/blueprints/index/rebuild`：遍历 `active` 蓝图异步全量重建 |

未配置 `EMBEDDING_API_BASE` / `EMBEDDING_API_KEY` 时：`embedding_status=skipped`，搜索降级为仅关键词 + 标量过滤。

### 3.5 混合打分

```text
硬过滤：kb_id + status=active + 标量标签 AND（与 list API 一致）
  ↓
关键词分：对 name / description / search_text ILIKE 匹配 keyword（多字段取 max）
向量分：cosine_similarity(embedding, embed(semantic_query))
  ↓
final_score = vector_weight × norm(vector_score) + keyword_weight × norm(keyword_score)
  ↓
仅返回 final_score > 0；按 score DESC 取 top_k
```

默认权重：`vector_weight=0.6`，`keyword_weight=0.4`，`top_k=10`（最大 50）。

---

## 4. API 契约

**前缀**：`/api/v1/kbs/{kb_id}/blueprints`  
**响应**：沿用 `success()` / `error()` envelope。

### 4.1 `POST /parse-search-query`

将自然语言拆分为结构化检索参数。无状态，不落库。

**请求**

```json
{
  "query": "找一份政务云方案的技术架构章节蓝图，偏正式风格"
}
```

**响应 data**

```json
{
  "semantic_query": "政务云 技术架构 章节 写作模板",
  "keyword": "政务云 技术架构",
  "product_tags": ["政务云"],
  "industry_tags": ["政府"],
  "scenario_tags": []
}
```

| 规则 | 说明 |
|------|------|
| 配置 | `blueprint_search_parse_model` / `blueprint_search_parse_timeout_sec`（默认对齐 `blueprint_suggest_*`） |
| 校验 | `query` 必填，1–500 字；空标签数组表示不过滤 |
| 错误 | `504` 超时；`502` LLM 失败 |

### 4.2 `POST /search`

混合检索核心接口。支持语义搜索流程（先 parse 再 search）或直接传参。

**请求**

```json
{
  "semantic_query": "政务云 技术架构 章节 写作模板",
  "keyword": "政务云 技术架构",
  "product_tags": ["政务云"],
  "industry_tags": [],
  "scenario_tags": [],
  "vector_weight": 0.6,
  "keyword_weight": 0.4,
  "top_k": 10
}
```

| 字段 | 默认 | 说明 |
|------|------|------|
| `vector_weight` | `0.6` | 向量分权重 |
| `keyword_weight` | `0.4` | 关键词分权重 |
| `top_k` | `10` | 返回条数上限，最大 50 |
| 标量过滤 | — | 请求中非空标签须全部被蓝图包含（AND） |

**响应 data**

```json
{
  "items": [
    {
      "blueprint_id": "...",
      "name": "政务云技术方案",
      "description": "...",
      "product_tags": ["政务云"],
      "industry_tags": ["政府"],
      "scenario_tags": [],
      "source_chapter_title": "技术架构",
      "version": 2,
      "updated_at": "2026-06-22T10:00:00+08:00",
      "embedding_status": "ready",
      "score": 0.87,
      "score_detail": {
        "vector_score": 0.92,
        "keyword_score": 0.78,
        "vector_weight": 0.6,
        "keyword_weight": 0.4
      },
      "highlights": [
        { "field": "name", "snippet": "政务云<em>技术架构</em>方案" },
        { "field": "search_text", "snippet": "...<em>政务云</em>平台..." }
      ]
    }
  ],
  "total": 3,
  "search_meta": {
    "vector_enabled": true,
    "keyword_enabled": true,
    "candidates_scanned": 42
  }
}
```

**高亮规则**：在 `name` / `description` / `search_text` 中对 `keyword` 按空格分词命中处包裹 `<em>`；每字段最多返回 1 条 snippet（截断至 200 字符）。

**校验**：`semantic_query` 与 `keyword` 不能同时为空 → `400`。

**降级**：Embedding 未配置时 `search_meta.vector_enabled=false`，`vector_score=0`。

### 4.3 `POST /index/rebuild`

| 项 | 说明 |
|----|------|
| 用途 | embedding 模型切换、历史蓝图补索引 |
| 行为 | 遍历 kb 下全部 `active` 蓝图，`BackgroundTasks` 异步逐条重建 |
| 响应 | `{ "queued": 15, "message": "rebuild started" }` |
| 权限 | V1 与蓝图 CRUD 同级 |

### 4.4 现有 API 扩展

- `GET /blueprints` 列表项可选增加 `embedding_status` 字段。
- `create` / `update` 路由增加 `BackgroundTasks` 触发索引；`delete` 依赖 CASCADE。

### 4.5 配置项（`config.py`）

```text
blueprint_search_parse_model      # 默认 qwen3.6-flash
blueprint_search_parse_timeout_sec  # 默认 30
embedding_model                   # 已有，复用 text-embedding-v2
```

---

## 5. 前端交互

### 5.1 列表页布局

在现有筛选表单**上方**增加语义搜索区：

```text
┌─ 目录蓝图 ─────────────────────────────────────────────┐
│ [语义搜索输入框                    ] [语义搜索] [返回列表] │
│ ── 筛选区（现有 keyword + 标签 + 查询/重置）────────── │
│ ── Table ──────────────────────────────────────────── │
└──────────────────────────────────────────────────────┘
```

### 5.2 模式与流程

| 状态 | 行为 |
|------|------|
| 普通模式（默认） | 现有筛选 + 分页；「返回列表」隐藏 |
| 语义搜索模式 | Table 展示 search Top N；显示匹配分；关闭分页；「返回列表」可见 |

**流程**：用户输入 → 点击「语义搜索」→ `parseSearchQuery` → `searchBlueprints`（默认权重）→ 进入语义搜索模式。

| 项 | 说明 |
|----|------|
| placeholder | 「用自然语言描述，如：政务云技术架构章节的正式风格蓝图」 |
| 默认权重 | `vector_weight=0.6`, `keyword_weight=0.4`, `top_k=10` |
| 解析中间态 | V1 不向用户展示 LLM 拆分参数 |
| 「返回列表」 | 清空语义状态，恢复普通过滤并 `listBlueprints` |

### 5.3 Table 列（语义搜索模式）

在现有列基础上临时增加：

| 列 | 说明 |
|----|------|
| 匹配分 | `score` 保留 2 位小数；Tooltip 展示 `score_detail` |
| 匹配摘要 | `highlights[0].snippet`，渲染 `<em>` 高亮 |

普通模式可选增加 **向量状态** 列（待处理 / 已完成 / 失败 / 跳过）。

### 5.4 API Client（`blueprints.ts`）

```typescript
parseBlueprintSearchQuery(kbId, { query })
searchBlueprints(kbId, BlueprintSearchParams)
rebuildBlueprintIndex(kbId)  // V1 无 UI，仅 client 预留
```

---

## 6. 错误处理

| 场景 | 处理 |
|------|------|
| Embedding API 未配置 | `embedding_status=skipped`；搜索仅关键词 + 标量 |
| 蓝图 `pending` | 参与关键词检索；`vector_score=0` |
| 蓝图 `failed` | 同上；列表展示失败状态 |
| LLM 解析失败 | toast 提示；不进入语义搜索模式 |
| 双查询为空 | `400` |
| 无匹配 | `items=[]`；空态「未找到匹配的目录蓝图」 |
| 删除蓝图 | FK CASCADE 清理 embedding |

---

## 7. 测试计划

### 7.1 后端单元测试

| 文件 | 覆盖 |
|------|------|
| `test_blueprint_embedding_task.py` | `search_text` 拼接、`content_hash`、upsert、skipped/failed |
| `test_blueprint_search_service.py` | 标量过滤、关键词分、向量分、权重融合、高亮、降级 |
| `test_blueprint_query_parse_service.py` | LLM JSON 解析、校验、超时 |

### 7.2 后端集成测试

| 文件 | 覆盖 |
|------|------|
| `test_blueprint_search_api.py` | parse / search / rebuild（mock embedding + LLM） |
| 扩展 `test_blueprint_api.py` | 创建/更新触发索引；删除后 embedding 消失 |

### 7.3 前端

- `BlueprintListPage` 组件测试（可选）：模式切换、返回列表、高亮渲染。

---

## 8. 文件清单

| 文件 | 职责 |
|------|------|
| `backend/alembic/versions/20260622_xxxx_blueprint_embeddings.py` | DDL |
| `backend/src/models/blueprint_embedding.py` | ORM |
| `backend/src/services/knowledge/blueprint_embedding_task.py` | 索引构建/重建 |
| `backend/src/services/knowledge/blueprint_search_service.py` | 混合检索 + 高亮 |
| `backend/src/services/knowledge/blueprint_query_parse_service.py` | LLM 解析 |
| `backend/src/api/schemas/blueprints.py` | 新增 schema |
| `backend/src/api/routes/blueprints.py` | 新端点 + BackgroundTasks |
| `backend/src/config.py` | parse 相关配置 |
| `frontend/src/services/blueprints.ts` | API client |
| `frontend/src/pages/Knowledge/BlueprintListPage.tsx` | 语义搜索 UI |

---

## 9. Constitution 对齐

| 原则 | 对齐方式 |
|------|----------|
| Knowledge Asset First | 检索对象为已确认保存的目录蓝图（`active`） |
| Human Confirmation Gate | 索引在蓝图 save 之后构建，不索引 generate 草稿 |
| Chapter-First | 蓝图本身即章节结构锚点；V1 蓝图级召回 |
| Retrieval Before Generation | 先交付可解释检索，为后续「蓝图推荐 → 目录建议」铺路 |
