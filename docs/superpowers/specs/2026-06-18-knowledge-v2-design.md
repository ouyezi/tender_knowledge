# Design: 知识库系统 V2（录入工作台 + 三表存储 + tender_skills 升级）

**Date**: 2026-06-18  
**Status**: Draft (brainstorming approved)  
**Related**: 用户 V2 需求规格说明书 · `specs/009-doc-chunk-integration/` · `docs/superpowers/specs/2026-06-16-doc-chunk-directory-sync-design.md`  
**Problem**: 在保留现有 KU/候选流的前提下，引入基于 doc_chunk 解析结果的新知识录入工作台、新浏览筛选页，以及 `knowledge_chunks` / `chunk_assets` / `chunk_embeddings` 三表存储；同步升级 tender_skills 依赖。

---

## 1. 背景与目标

### 1.1 现状

| 层 | 状态 |
|----|------|
| 文档解析 | `tender_skills` → doc_chunk 工作区 → `import_workspace` → `documents` / `document_tree_nodes` / 候选等 |
| 知识正式库 | `knowledge_units`（经 `CandidateConfirmPage` 确认入库） |
| 检索索引 | `retrieval_index_entries`（BM25 + 向量，按 `kb_id` 隔离） |
| 章节预览 | `content_md_store` + `section_slice` + `outline_node_content_service`（Bid Outline 场景） |
| 前端 | `/knowledge`（KU/Wiki/Manual）、`/candidates`（候选确认）；全局 `KBContext` |

### 1.2 产品目标（本迭代）

1. **tender_skills 升级**：依赖升至最新版本，梳理调用点，解析能力无降级。
2. **知识录入 V2**：三栏工作台——文档目录树、章节 Markdown 预览、AI 预填属性表单；支持父/子节点入库与版本覆盖。
3. **知识浏览 V2**：组合筛选列表 + 详情（版本链、关联资产）。
4. **三表存储**：`knowledge_chunks`、`chunk_assets`、`chunk_embeddings` 替代 V2 场景下的臃肿单表方案。
5. **资产预写**：解析导入时预写 `chunk_assets`；录入预览可展示；**不做** 2.4 独立资产提取页。

### 1.3 已锁定决策（brainstorming）

| 议题 | 决议 |
|------|------|
| 与旧体系 | V2 工作台新录入；KU/候选流保留；旧表后续再删 |
| 检索 | 本迭代**不**双写 `retrieval_index_entries`；后续用新表字段做关系查询并重做检索 |
| 多租户 | `knowledge_chunks` 挂 `kb_id`；API：`/api/v1/kbs/{kb_id}/knowledge-chunks/*` |
| 目录树数据源 | DB：`documents` + `document_tree_nodes` |
| 正文预览 | `content.md`（`content_md_store`）+ `section_slice` |
| 可选文档 | 全部 `parse_status=ready` 且存在树节点的文档 |
| 资产提取页（2.4） | 不做；资产由 import 流水线预写 |

### 1.4 不在范围

- `retrieval_index_entries` 双写或新检索 API
- 2.4 独立资产提取页、OCR 手工修正 UI
- 旧 KU/候选流下线与旧数据迁移
- legacy 解析路径（`USE_DOC_CHUNK_PARSE=false`）废弃

---

## 2. 方案对比与决议

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **① 平行模块（推荐）** | 新 models/services/routes/前端页；复用 `section_slice`、`content_md_store`、LLM；旧链路零改动 | 风险低、可分期交付 | 短期两套知识模型并存 |
| ② 在候选流上改造 | 扩展 `CandidateConfirmPage` 与 `knowledge_units` | 复用页面骨架 | 字段/版本语义差异大，改造成本高 |
| ③ Big Bang 替换 | 新表上线同时废弃 KU/候选/旧检索 | 架构干净 | 范围爆炸，与保留旧流冲突 |

**决议：方案 ①**

实现路径：在 `backend/src/services/knowledge_v2/` 建独立服务层；前端新增 `/knowledge-v2/entry`、`/knowledge-v2/browse`；现有 `/knowledge`、`/candidates` 不动。

---

## 3. 架构与边界

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend                                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────┐ │
│  │ KnowledgeEntry   │  │ KnowledgeBrowse  │  │ 旧页面保留  │ │
│  │ (三栏工作台)      │  │ (筛选+详情)       │  │ KU/Candidate│ │
│  └────────┬─────────┘  └────────┬─────────┘  └────────────┘ │
└───────────┼─────────────────────┼───────────────────────────┘
            │                     │
            ▼                     ▼
┌───────────────────────────────────────────────────────────────┐
│  API  /api/v1/kbs/{kb_id}/knowledge-chunks/*  (新)            │
│       /api/v1/kbs/{kb_id}/knowledge-units/*     (旧，不动)     │
└───────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────┐     ┌──────────────────────┐
│ knowledge_chunks    │     │ retrieval_index_     │
│ chunk_assets        │     │ entries (旧检索，本迭代│
│ chunk_embeddings    │     │ 不写 V2 数据)         │
└─────────────────────┘     └──────────────────────┘
            ▲
            │ 读取
┌───────────┴──────────────────────────────────────────┐
│ documents + document_tree_nodes + content.md           │
│ (doc_chunk import 已落库；tender_skills 升级对齐)         │
└──────────────────────────────────────────────────────┘
```

**tender_skills 升级**：与 V2 同迭代、独立子任务；沿用 009 + directory-sync 模式（依赖对齐 → fixture → 调用点梳理）；不阻塞 V2 表/API 开发，验收前需解析无降级。

---

## 4. 数据模型

### 4.1 ID 与映射（相对原规格的修正）

| 规格字段 | 实现映射 |
|---------|---------|
| `doc_id` | `documents.document_id`（UUID，API 用 string） |
| `primary_node_id` | `document_tree_nodes.node_id`（UUID string） |
| 去重键 | `(kb_id, doc_id, primary_node_id)` WHERE `is_latest = true` |
| 版本号 | `{major}.{minor}` 字符串；新建 `1.0`，覆盖 minor+1（如 `1.1`） |

### 4.2 主表 `knowledge_chunks`

在用户需求规格字段基础上**增补**：

- `kb_id UUID NOT NULL`（FK 逻辑关联 `knowledge_bases.kb_id`）

其余字段按需求规格 §3.1 建表。枚举值：

- `knowledge_type`: fact, template, solution, case, table, image
- `content_type`: text, mixed
- `source_type`: bid, proposal, qualification, contract, manual, wiki, case
- `category`: qualification, technical, business, legal, personnel, price, case, template
- `status`: draft, active, deprecated, disabled
- `security_level`: public, internal, confidential
- `review_status`: pending, approved, rejected（默认 approved）
- `quote_mode`: full, partial
- `template_type`: commitment, authorization, response, technical_solution, implementation_plan, service_plan, quotation

`catalog_path` JSONB 结构：

```json
[
  {"node_id": "uuid", "title": "第一章", "level": 1},
  {"node_id": "uuid", "title": "1.1 资质", "level": 2}
]
```

### 4.3 资产表 `chunk_assets`

在需求规格 §3.2 基础上**增补**定位与租户字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `kb_id` | UUID | 知识库隔离 |
| `doc_id` | UUID | FK `documents.document_id` |
| `page_start` | Integer | 可空 |
| `page_end` | Integer | 可空 |
| `char_start` | Integer | 字符起点 |
| `char_end` | Integer | 字符终点 |

- 导入后 `chunk_id = NULL`；知识入库后批量 `UPDATE chunk_id`。
- `allow_row_filter` 默认 `false`。
- 图片 `image_storage_url` 为相对路径（如 `/storage/images/xxx.png` 或现有 media 存储路径）。

### 4.4 向量表 `chunk_embeddings`

| 字段 | 说明 |
|------|------|
| `object_type` | chunk \| asset |
| `object_id` | 对应 `knowledge_chunks.id` 或 `chunk_assets.id` |
| `content_embedding` | Vector（阿里云 text-embedding-v2，维度随模型） |
| `summary_embedding` | Vector，可空 |

唯一约束：`(object_type, object_id)`。

### 4.5 索引与约束

```sql
-- knowledge_chunks：同一 KB、同一文档节点仅一条最新版
CREATE UNIQUE INDEX uq_knowledge_chunks_latest_node
  ON knowledge_chunks (kb_id, doc_id, primary_node_id)
  WHERE is_latest = true;

-- chunk_assets：章节范围匹配
CREATE INDEX ix_chunk_assets_doc_range
  ON chunk_assets (kb_id, doc_id, char_start, char_end);

-- chunk_embeddings
CREATE UNIQUE INDEX uq_chunk_embeddings_object
  ON chunk_embeddings (object_type, object_id);
```

**DDL 策略**：直接执行新表 DDL，不考虑旧 V2 表数据兼容（当前无此三表）。

---

## 5. 后端服务

### 5.1 模块结构

```text
backend/src/services/knowledge_v2/
├── entry_content_service.py    # 树加载、章节切片、资产范围查询
├── prefill_service.py          # LLM 预填（10s 超时、JSON 解析）
├── chunk_service.py            # 入库、版本链、去重、token_count
├── asset_link_service.py       # 章节范围匹配 chunk_assets ↔ chunk
├── asset_seed_service.py       # import 时从 workspace 预写 chunk_assets
└── embedding_task.py           # 异步向量写入 chunk_embeddings
```

### 5.2 `entry_content_service`

- `list_entry_documents(kb_id)`：`parse_status=ready` 且存在 `document_tree_nodes`。
- `get_document_tree(kb_id, doc_id)`：仅 `node_type=heading` 建树；节点附带 `ingested: bool`（查 `knowledge_chunks` 且 `is_latest=true`）。
- `get_node_preview(kb_id, doc_id, node_id)`：
  - `load_content_md(document_id)`
  - 新增 `outline_nodes_from_tree_nodes`，调用 `slice_section_markdown`
  - 父节点：合并子树全部内容（按 `sort_order`）
  - 返回：`title`, `content_md`, `content_type`（含图/表为 mixed）, `char_start/end`, `page_start/end`, `catalog_path`, `assets[]`
- 位置信息：优先 linkage/workspace 元数据；缺失时用切片 char offset；`page_*` 可空。

### 5.3 `prefill_service`

- 模型：`qwen3-max`（配置项 `KNOWLEDGE_PREFILL_MODEL`）
- 超时：**10 秒**（`KNOWLEDGE_PREFILL_TIMEOUT_SEC=10`）
- 超时或失败：返回部分字段 + `warnings: ["prefill_timeout"]`；不阻断手工填写
- 允许留空：`industries`, `products`, `customer_types`, `regions`, `expire_date`
- 输出经 JSON Schema 校验；非法枚举回退默认值

### 5.4 `chunk_service`

- `content_hash`：SHA256(normalize(content))
- `token_count`：千问兼容 tokenizer（实现选轻量方案，验收抽样比对）
- 新建：`knowledge_code=uuid4()`, `version=1.0`, `is_latest=true`
- 覆盖：旧记录 `is_latest=false`；新记录 `version` minor+1；`previous_version_id` 指向旧记录
- 同步入库目标 < 2s（不含 AI 预填、不含 embedding）
- 入库后调用 `asset_link_service` 关联范围内 `chunk_assets`

### 5.5 `asset_seed_service`（挂 `import_workspace` 末尾）

- 扫描 workspace `images/manifest.json` 与 chunks 内 table blocks
- 写入 `chunk_assets`（`chunk_id=NULL`），带 `kb_id`, `doc_id`, 位置信息
- 图片路径复用 `DocumentMediaAsset` 存储或复制至约定目录
- 表格写 `raw_markdown`；`llm_summary` 本迭代可空

### 5.6 `embedding_task`

- 触发：`POST /knowledge-chunks` 成功后 `BackgroundTasks`
- 对 chunk 的 `content` 与 `summary` 各生成向量，UPSERT `chunk_embeddings`
- 已关联 assets 同理（`object_type=asset`）
- 失败记日志，不阻断入库；详情可返回 `embedding_status: pending|ready|failed`

---

## 6. API 契约

前缀：`/api/v1/kbs/{kb_id}/knowledge-chunks`  
响应格式：沿用现有 `success()` envelope + `trace_id`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/entry/documents` | 可录入文档列表 |
| GET | `/entry/documents/{doc_id}/tree` | 目录树 + `ingested` 标记 |
| GET | `/entry/documents/{doc_id}/nodes/{node_id}/preview` | 章节预览 + 范围内 assets |
| POST | `/prefill` | AI 预填属性 |
| POST | `/` | 创建/覆盖（body 含 `force: bool`） |
| GET | `/` | 列表 + 组合筛选 + 关键词 |
| GET | `/{chunk_id}` | 详情 + `previous_version` + `assets` |
| GET | `/chunk-assets` | `doc_id` + 位置范围查询 |

### 6.1 `POST /prefill`

**请求**

```json
{
  "doc_id": "uuid",
  "primary_node_id": "uuid",
  "content": "章节完整 markdown",
  "metadata": {
    "source_type": "bid",
    "file_name": "xxx.docx",
    "project_name": "..."
  }
}
```

**响应**：预填字段 JSON；超时 10s 内部分字段可为 null/空；附 `warnings` 数组。

### 6.2 `POST /`

- 无冲突：201，返回 `id`, `version`, `knowledge_code`
- 已存在 `is_latest=true` 且 `force≠true`：**409**，body 含现有 `id`, `version`
- `force=true`：执行版本覆盖

请求体包含所有可编辑字段（见需求规格 §2.2.3）；`content` 由预览提供、前端只读提交。

### 6.3 `GET /` 筛选参数

`category`, `knowledge_type`, `source_type`, `status`, `products[]`, `industries[]`, `regions[]`, `tags[]`, `security_level`, `is_template`, `winning_flag`, `review_status`, `issue_date_from`, `issue_date_to`, `expire_date_from`, `expire_date_to`, `keyword`（匹配 title/summary）, `page`, `page_size`

默认排序：`update_time DESC`。

列表字段：`id`, `title`, `version`, `category`, `knowledge_type`, `status`, `token_count`, `update_time`。

### 6.4 `GET /{chunk_id}`

完整字段 + `previous_version` 概要 + `assets` 列表 + `embedding_status`。

---

## 7. 前端

### 7.1 路由

| 路径 | 组件 | 说明 |
|------|------|------|
| `/knowledge-v2/entry` | `KnowledgeEntryPage` | 三栏录入工作台 |
| `/knowledge-v2/browse` | `KnowledgeBrowsePage` | 筛选列表 |
| `/knowledge-v2/browse/:chunkId` | Drawer 或子路由 | 详情 |

`AppShell` 导航增加「知识录入 V2」「知识浏览 V2」。旧 `/knowledge`、`/candidates` 保留。

### 7.2 录入页交互

1. 顶部 Select 选文档 → 左侧 `Tree` 展示目录
2. 点击节点 → 中间加载 Markdown 预览（含图片缩略图、表格）
3. 点击「添加到知识库」→ 右侧展开，显示「AI 预填中…」
4. 预填完成 → 表单可编辑（`content` 只读）
5. 「确认添加」→ 成功 Toast + 树节点 `ingested` 标记
6. 409 → `Modal.confirm` 覆盖提示

### 7.3 浏览页

- 顶部全部筛选项；`products`/`industries`/`regions`/`tags` 多选
- 表格 + 分页；点击进入详情
- 筛选方案：`localStorage` key `knowledge-v2-filters:{kb_id}`，支持命名保存/加载/删除

### 7.4 权限

沿用 `KBContext` 选库；本迭代不新增 RBAC 层（符合「无额外权限阻碍」）。

---

## 8. 错误处理

| 场景 | 行为 |
|------|------|
| LLM 预填超时/失败 | 200 + 部分字段 + warning；前端 Toast 提示手工补充 |
| content.md 缺失 | 预览 404，提示文档未解析完成 |
| 重复入库未确认 | 409 + 覆盖确认弹窗 |
| embedding 未配置 | 跳过向量，入库仍成功 |
| import 资产种子失败 | warning 日志；录入可进行（纯文本） |

---

## 9. tender_skills 升级（子任务）

1. 升级 `backend/pyproject.toml` 中 `doc-chunk @ file:../../tender_skills` 至目标 commit
2. 梳理调用点：`pipeline_runner`, `import_service`, mappers, `chunk_classification_service`, `actual_bid_parse_runner`
3. 刷新 `tests/fixtures/doc_chunk_workspace_minimal/`
4. 跑通 `test_doc_chunk_*`, `test_actual_bid_parse*`
5. **不改动** legacy 解析路径

---

## 10. 测试与验收

### 10.1 测试计划

| 层级 | 覆盖 |
|------|------|
| 单元 | 树节点 section 适配、版本递增、去重、资产范围匹配、prefill JSON 解析 |
| 集成 | 录入全流程（mock LLM）、409 覆盖、列表筛选组合 |
| 契约 | 新 API envelope 格式 |
| 回归 | 旧 KU/候选 API 无变化；doc_chunk import 仍绿 |

### 10.2 验收标准映射（需求规格 §6）

| # | 标准 | 本设计对应 |
|---|------|-----------|
| 1 | tender_skills 升级后解析无降级 | §9 |
| 2 | 父/叶子节点预览正确拼接 | §5.2 + §7.2 |
| 3 | 预填 10s、部分字段可空 | §5.3 |
| 4 | 覆盖版本链正确 | §5.4 + 单元测试 |
| 5 | 资产预览（无独立提取页） | §5.5 + §5.2 |
| 6 | 筛选页多条件准确 | §6.3 + §7.3 |
| 7 | 向量异步不影响入库 | §5.6（检索召回延后） |
| 8 | 无权限阻碍 | §7.4 |

---

## 11. 配置项（新增）

| 环境变量 | 默认 | 说明 |
|---------|------|------|
| `KNOWLEDGE_PREFILL_MODEL` | `qwen3-max` | 预填专用模型 |
| `KNOWLEDGE_PREFILL_TIMEOUT_SEC` | `10` | 预填超时 |
| `EMBEDDING_API_BASE` | （已有） | 阿里云 embedding 端点 |
| `EMBEDDING_API_KEY` | （已有） | embedding 密钥 |

---

## 12. 后续迭代（显式延后）

- 基于 `knowledge_chunks` 的新检索 API（关系查询 + 向量召回）
- `retrieval_index_entries` 下线或迁移
- 2.4 独立资产提取页（OCR、表格 LLM 摘要、手工修正）
- 旧 KU/候选流废弃
