# Design: 知识块检索（Knowledge Chunk Retrieval）

**Date**: 2026-06-23  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-18-knowledge-v2-design.md` · `docs/superpowers/specs/2026-06-22-blueprint-semantic-search-design.md` · `backend/src/services/knowledge/embedding_task.py`

---

## 1. 背景与目标

### 1.1 痛点

| 痛点 | 说明 |
|------|------|
| 知识块未完善即入库 | 入库后仅有原始正文；图片资产缺少 OCR/说明；摘要可能未覆盖图片信息 |
| 无主动索引入口 | 向量在入库时后台静默生成，用户无法控制「何时可检索」 |
| 列表检索能力弱 | 知识浏览页仅支持 `ILIKE` 关键词 + 标量过滤，无法理解语义相近表达 |
| 向量粒度不足 | 现有 `chunk_embeddings` 仅有 content/summary 两路向量，title 未单独索引 |

### 1.2 产品定位

为**知识浏览页**提供两项能力：

1. **构建索引**：用户手动触发，完善知识（视觉提取图片 → 更新摘要/有效期 → 构建 title/summary/content 向量），完成后 `embedding_status=ready` 表示「已索引、可语义检索」。
2. **语义搜索**：自然语言查询经 LLM 拆分为向量语句与关键词，通过可配置权重的混合检索返回 Top N 知识块。

### 1.3 建设目标

1. **索引流水线**：列表项「构建索引」按钮；视觉模型 + MD5 全局缓存；LLM 重写摘要；三向量写入；状态可追踪。
2. **语义检索**：`parse-search-query` + `search` API；仅命中 `embedding_status=ready` 且 `is_latest=true` 的知识块。
3. **浏览页入口**：语义搜索区；构建索引操作列；搜索结果覆盖 Table 展示分数与高亮。

### 1.4 已锁定决策（brainstorming）

| 议题 | 决议 |
|------|------|
| 已索引标识 | A. 复用 `embedding_status=ready`；`status`（draft/active/…）独立管生命周期 |
| 索引触发 | A. 纯手动；取消 `POST /knowledge-chunks` 入库后自动 embedding |
| 向量粒度 | A. 新增 `title_embedding`；检索时 title/summary/content 分别算分再按权重合并 |
| 图片理解 | A. 视觉模型结构化输出 caption / ocr / facts；MD5 全局缓存 |
| 摘要/有效期 | A. LLM 重写 summary；高置信才更新 issue_date / expire_date |
| 查询解析 | B. 仅 `semantic_query` + `keyword`；标量过滤仍由浏览页手动筛选 |
| 实现方案 | ① 独立索引/检索服务（与蓝图语义检索模式一致） |

### 1.5 不在范围（V1）

- 语义搜索自动解析标量过滤（category、products 等）
- 权重调节 UI 面板
- 语义搜索历史记录
- 资产级 / 节点级独立检索
- 批量构建索引
- 全库 `index/rebuild` 端点
- 复用 Epic5 多态 `retrieval_index_entries` 框架
- E2E 自动化测试

---

## 2. 方案对比与决议

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **① 独立索引/检索服务（推荐）** | `chunk_index_task` + `image_vision_service` + `image_extraction_cache` + `chunk_search_service` + `chunk_query_parse_service` | 与蓝图语义检索分层一致；职责清晰；可独立测试 | 新增 4～5 个 service + migration |
| ② 扩展现有 `embedding_task` | 在 `embed_knowledge_chunk` 内塞入视觉提取与摘要更新 | 改动文件少 | 单函数职责过重；难以表达 indexing 中间态 |
| ③ 接入 Epic5 多态检索 | 统一写入 `retrieval_index_entries` | 未来可统一全库检索 | Epic5 表已清理；scope 过重 |

**决议：方案 ①**

---

## 3. 架构与数据模型

### 3.1 总体架构

```text
KnowledgeBrowsePage
  ├─ 普通过滤 → GET /knowledge-chunks（现有 ILIKE + 标量）
  ├─ [构建索引] → POST /knowledge-chunks/{id}/index（异步）
  └─ 语义搜索
       ① POST /knowledge-chunks/parse-search-query  → semantic_query + keyword
       ② POST /knowledge-chunks/search              → 混合检索 + 排序 + 高亮
       ③ 覆盖 Table 展示 Top N；「返回列表」恢复普通过滤

chunk_index_task（BackgroundTasks）
  ① knowledge_chunks.embedding_status → indexing
  ② 图片资产 → MD5 查/写 image_extraction_cache → 更新 chunk_assets
  ③ LLM 重写 summary + 条件更新 issue_date / expire_date
  ④ EmbeddingClient → title / summary / content 向量 UPSERT chunk_embeddings
  ⑤ embedding_status → ready | failed

knowledge_chunks POST /（create）
  └─ 不再触发 BackgroundTasks embed；新记录 embedding_status=pending
```

### 3.2 `knowledge_chunks` 扩展

| 字段 | 类型 | 说明 |
|------|------|------|
| `embedding_status` | varchar(20) | `pending` / `indexing` / `ready` / `failed` / `skipped`；默认 `pending` |
| `indexed_at` | timestamptz | 最近一次索引完成时间；可空 |

**说明**：详情 API 此前通过查询 `chunk_embeddings` 计算 `embedding_status`；本特性改为读 `knowledge_chunks.embedding_status` 为权威来源，与列表展示一致。

### 3.3 `chunk_embeddings` 扩展（`object_type=chunk`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `title_embedding` | vector(1024) | 对 `knowledge_chunks.title` 的向量；新增 |
| `content_hash` | varchar(64) | `SHA256(title + "\n" + summary + "\n" + content)`；变更检测 |

保留现有 `content_embedding`（正文）、`summary_embedding`（摘要）。  
`object_type=asset` 的 embedding 行不在 V1 索引流水线中重建（检索仅针对 chunk 级）。

### 3.4 新表 `image_extraction_cache`

全局跨知识库共享，按图片文件 MD5 去重。

| 字段 | 类型 | 说明 |
|------|------|------|
| `md5_hash` | varchar(32) PK | 图片文件字节 MD5（hex） |
| `caption` | text | 图片内容描述 |
| `ocr_text` | text | 图中识别文字 |
| `extracted_facts` | jsonb | 结构化事实，如证书名称、有效期等 |
| `vision_model` | varchar(64) | 使用的视觉模型名 |
| `created_at` | timestamptz | 首次提取时间 |

### 3.5 `chunk_assets` 扩展

| 字段 | 类型 | 说明 |
|------|------|------|
| `extracted_facts` | jsonb | 从 `image_extraction_cache` 复制的结构化事实；可空 |

索引流水线写入规则：

| 视觉输出 | 写入字段 |
|----------|----------|
| caption | `image_caption` |
| ocr_text | `image_ocr_text` |
| extracted_facts | `extracted_facts` |

### 3.6 索引生命周期

| 事件 | 行为 |
|------|------|
| 知识块创建 | `embedding_status=pending`；**不**自动 embedding |
| 用户点击构建索引 | `POST .../index` → `indexing` → 后台 `index_knowledge_chunk` |
| 索引成功 | `embedding_status=ready`，`indexed_at=now()` |
| 索引失败 | `embedding_status=failed`；保留已有向量（若曾 ready） |
| 知识块删除 / purge | 随 FK 删除 `chunk_embeddings`；`image_extraction_cache` 保留（全局复用） |
| 重复点击构建索引 | `indexing` 中返回 **409**；`ready` 允许强制重建（`force=true` 可选，V1 默认允许直接重建） |

未配置 embedding API：`embedding_status=skipped`，语义搜索不可用（仅关键词降级或无结果）。  
未配置 vision API：跳过图片提取步骤，仍执行摘要重写（不含图片信息）与向量索引。

---

## 4. 索引流水线

### 4.1 模块结构

```text
backend/src/services/knowledge/
├── chunk_index_task.py           # 编排：index_knowledge_chunk
├── image_vision_service.py       # 视觉模型调用 + JSON 解析
├── image_extraction_cache.py     # MD5 查/写缓存
├── chunk_summary_service.py      # LLM 重写 summary + 条件更新日期
├── chunk_query_parse_service.py  # 语义搜索查询拆分
├── chunk_search_service.py       # 混合检索
└── chunk_index_text.py           # 关键词分、高亮（类比 blueprint_index_text）
```

### 4.2 图片提取

1. 查询 `chunk_assets` 中 `chunk_id` 关联且 `asset_type=image` 的记录。
2. 通过 `image_storage_url` 解析本地 storage 路径，读取文件字节，计算 MD5。
3. 查 `image_extraction_cache`：
   - **命中**：复制 caption / ocr / facts 到 `chunk_assets`。
   - **未命中**：调用视觉模型（默认 `qwen-vl-max`，配置项 `KNOWLEDGE_VISION_MODEL`），解析 JSON 响应，写入 cache 与 asset。
4. 视觉模型 prompt 要求输出 JSON：

```json
{
  "caption": "图片内容描述",
  "ocr_text": "图中文字",
  "extracted_facts": {
    "cert_name": "ISO9001",
    "issue_date": "2023-01-01",
    "expire_date": "2026-01-01",
    "confidence": "high"
  }
}
```

`extracted_facts.confidence` 取值 `high` / `medium` / `low`；仅 `high` 时用于更新 chunk 日期字段。

配置项：

| 配置 | 默认 | 说明 |
|------|------|------|
| `KNOWLEDGE_VISION_MODEL` | `qwen-vl-max` | OpenAI 兼容 multimodal chat |
| `KNOWLEDGE_VISION_TIMEOUT_SEC` | `60` | 单图超时 |
| `KNOWLEDGE_VISION_MAX_IMAGES` | `20` | 单 chunk 索引最多处理图片数 |

### 4.3 摘要与有效期更新

调用文本 LLM（默认 `qwen3-max`，复用 `knowledge_prefill_model` 或独立 `KNOWLEDGE_INDEX_SUMMARY_MODEL`）：

**输入**：`title`、原 `summary`、`content`、各图片的 caption/ocr/facts 摘要。

**输出 JSON**：

```json
{
  "summary": "重写后的知识块摘要（200字以内）",
  "issue_date": "2023-01-01",
  "expire_date": "2026-01-01",
  "date_confidence": "high"
}
```

**规则**：

- 始终更新 `knowledge_chunks.summary`（除非 LLM 失败，则保留原值并记 warning）。
- `issue_date` / `expire_date`：仅当 `date_confidence=high` 且对应字段非空时覆盖；否则保留原值。
- 超时（默认 30s）不阻断向量步骤；使用原 summary 继续。

### 4.4 向量写入

1. 计算 `content_hash`。
2. 若 hash 与 `chunk_embeddings` 中一致且三向量均已存在，可跳过 embed API（仍更新 `embedding_status=ready`）。
3. 分别 embed：`title`、`summary`（更新后）、`content`。
4. UPSERT `chunk_embeddings`（`object_type=chunk`，`object_id=chunk.id`）。

取消入库时 `_embed_chunk_in_background` 调用；`embed_knowledge_chunk` 可保留供单元测试，或重构为 `chunk_index_task` 内部步骤。

---

## 5. 语义检索

### 5.1 硬过滤

```text
kb_id = 当前知识库
AND is_latest = true
AND embedding_status = 'ready'
```

**不**自动合并浏览页标量筛选；语义搜索与手动筛选互斥（前端切换模式，与蓝图列表一致）。

### 5.2 混合打分

```text
关键词分 keyword_score：
  ILIKE 匹配 title（权重 chunk_search_title_keyword_weight，默认 3.0）
        summary、content（权重 chunk_search_body_keyword_weight，默认 1.0）
  多字段取 max

向量分 vector_score：
  query_vec = embed(semantic_query)
  raw_v = w_title × cos(title_emb, query_vec)
        + w_summary × cos(summary_emb, query_vec)
        + w_content × cos(content_emb, query_vec)
  默认 w_title=0.25, w_summary=0.35, w_content=0.40

final_score = vector_weight × norm(raw_v) + keyword_weight × norm(keyword_score)
  ↓
可选 exact_match_bonus（title 完全包含 keyword 时加分，默认 0.35）
  ↓
raw_v max < chunk_search_vector_min_similarity（默认 0.10）时向量分量归零
  ↓
final_score > 0；按 DESC 取 top_k
```

**默认请求权重**：`vector_weight=0.6`，`keyword_weight=0.4`，`top_k=10`（最大 50）。

未配置 embedding：`search` 降级为仅关键词分排序；若无 keyword 则返回空列表。

### 5.3 查询解析

`chunk_query_parse_service` 类比 `blueprint_query_parse_service`，system prompt 仅要求：

```json
{
  "semantic_query": "用于向量检索的核心概念",
  "keyword": "2-5个关键词，空格分隔字符串"
}
```

配置：`chunk_search_parse_model`（默认 `qwen3.6-flash`）、`chunk_search_parse_timeout_sec`（30）、`chunk_search_parse_query_max`（500）。

---

## 6. API 契约

**前缀**：`/api/v1/kbs/{kb_id}/knowledge-chunks`  
**响应**：沿用 `success()` / `error()` envelope + `trace_id`。

### 6.1 `POST /{chunk_id}/index`

触发异步索引。

**请求**

```json
{
  "force": false
}
```

| 字段 | 说明 |
|------|------|
| `force` | 可选；`ready` 状态下默认允许重建；`indexing` 中返回 409 |

**响应 data**

```json
{
  "chunk_id": 123,
  "embedding_status": "indexing"
}
```

| 错误 | 说明 |
|------|------|
| 404 | chunk 不存在或不属当前 kb |
| 409 | 已在 indexing |

### 6.2 `GET /` 列表扩展

列表项新增字段：

```json
{
  "embedding_status": "pending",
  "indexed_at": null
}
```

### 6.3 `POST /parse-search-query`

**请求**

```json
{
  "query": "餐饮行业的食品经营许可证相关要求"
}
```

**响应 data**

```json
{
  "semantic_query": "食品经营许可证 资质要求 餐饮",
  "keyword": "食品经营许可证 餐饮"
}
```

| 错误 | 说明 |
|------|------|
| 504 | 解析超时 |
| 502 | LLM 失败或未配置 |

### 6.4 `POST /search`

**请求**

```json
{
  "semantic_query": "食品经营许可证 资质要求",
  "keyword": "食品经营许可证",
  "vector_weight": 0.6,
  "keyword_weight": 0.4,
  "title_vector_weight": 0.25,
  "summary_vector_weight": 0.35,
  "content_vector_weight": 0.4,
  "top_k": 10
}
```

**响应 data**

```json
{
  "items": [
    {
      "id": 123,
      "title": "...",
      "summary": "...",
      "category": "qualification",
      "knowledge_type": "fact",
      "status": "active",
      "embedding_status": "ready",
      "score": 0.82,
      "score_detail": {
        "keyword_score": 0.9,
        "vector_score": 0.75,
        "title_vector": 0.8,
        "summary_vector": 0.7,
        "content_vector": 0.72
      },
      "highlights": ["...<em>食品经营</em>..."]
    }
  ],
  "total": 1
}
```

---

## 7. 前端

### 7.1 知识浏览页 `KnowledgeBrowsePage`

| 区域 | 变更 |
|------|------|
| 操作列 | 新增「构建索引」按钮；`indexing` 显示 loading；`ready` 显示「重新索引」 |
| 状态列 | 新增 `embedding_status` Tag（待索引 / 索引中 / 已索引 / 失败） |
| 语义搜索区 | 顶部 Input + 搜索按钮；流程对齐 `BlueprintListPage` |
| 搜索结果 | 覆盖 Table；列含 score、highlights；「返回列表」恢复普通过滤 |

### 7.2 详情抽屉

- 索引完成后刷新 `summary`、`issue_date`、`expire_date`、资产图片字段。
- `embedding_status` 枚举扩展：`indexing`、`skipped`（前端 `knowledgeChunkMeta.ts` 同步）。

### 7.3 服务层

`frontend/src/services/knowledgeChunks.ts` 新增：

- `indexKnowledgeChunk(kbId, chunkId)`
- `parseChunkSearchQuery(kbId, body)`
- `searchKnowledgeChunks(kbId, body)`

---

## 8. 错误处理与可观测性

| 场景 | 行为 |
|------|------|
| 视觉单图失败 | 记 warning，跳过该图，继续其余步骤 |
| 摘要 LLM 失败 | 保留原 summary，继续向量步骤 |
| embedding 失败 | `embedding_status=failed`；不更新 `indexed_at` |
| 索引全程无 LLM/vision | 尽可能完成可用步骤；最终状态如实反映 |
| 日志 | 结构化：`trace_id`、`chunk_id`、`step`、`elapsed_ms`、`image_md5`（命中/未命中 cache） |

---

## 9. 测试策略

| 类型 | 覆盖 |
|------|------|
| 单元 | `image_extraction_cache` MD5 命中；`chunk_summary_service` JSON 解析与日期条件更新；`chunk_search_service` 三向量加权与 norm；`chunk_query_parse_service` |
| 单元 | `chunk_index_task` 编排（mock vision/LLM/embed） |
| 契约 | `POST /index` 状态流转；`POST /search` 仅返回 ready；create 不再触发 embed |
| 回归 | 移除 auto-embed 后现有 `test_knowledge_embedding` 调整 |

---

## 10. Constitution Check

| Gate | 验证 |
|------|------|
| G1 Spec-Driven | 本 spec 批准后再编码 |
| G2 Knowledge Asset | 以 KnowledgeChunk 为检索对象，非原始文件 |
| G3 Human Confirmation | 索引不自动发布；`status` 仍人工管理 |
| G4 Chapter & Trace | 检索结果含 chunk_id、catalog_path；日志带 trace_id |
| G5 Retrieval First | 本特性核心为检索能力增强 |
| G6 MVP Scope | 单 chunk 手动索引；无批量/文件夹导入 |

---

## 11. 配置汇总（`.env` / `config.py`）

```text
KNOWLEDGE_VISION_MODEL=qwen-vl-max
KNOWLEDGE_VISION_TIMEOUT_SEC=60
KNOWLEDGE_VISION_MAX_IMAGES=20
KNOWLEDGE_INDEX_SUMMARY_MODEL=qwen3-max
KNOWLEDGE_INDEX_SUMMARY_TIMEOUT_SEC=30
CHUNK_SEARCH_PARSE_MODEL=qwen3.6-flash
CHUNK_SEARCH_PARSE_TIMEOUT_SEC=30
CHUNK_SEARCH_PARSE_QUERY_MAX=500
CHUNK_SEARCH_TITLE_KEYWORD_WEIGHT=3.0
CHUNK_SEARCH_BODY_KEYWORD_WEIGHT=1.0
CHUNK_SEARCH_VECTOR_MIN_SIMILARITY=0.10
CHUNK_SEARCH_EXACT_MATCH_BOOST=0.35
```

Embedding 复用现有 `EMBEDDING_MODEL` / `EMBEDDING_API_*`。
