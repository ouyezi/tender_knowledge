# Design: 撰写技巧（Writing Technique）

**Date**: 2026-06-26  
**Status**: Approved (brainstorming)  
**Related**: `docs/superpowers/specs/2026-06-21-directory-blueprint-design.md` · `docs/superpowers/specs/2026-06-23-knowledge-chunk-retrieval-design.md`  
**Problem**: 知识块沉淀了标书写作经验，但缺少从知识块提炼「可复用写作方法论」的独立资产形态；目录蓝图解决章节目录组织，无法指导「某一类章节该怎么落笔」。

---

## 1. 背景与目标

### 1.1 痛点

| 痛点 | 说明 |
|------|------|
| 经验难以复用 | 优秀章节的写作思路、组织策略散落在知识块正文中 |
| AI 生成缺指导 | 生成时缺少「怎么写、写什么、注意什么」的结构化输入 |
| 与目录蓝图分工不清 | 目录蓝图管目录树；写作方法论需要独立扁平资产 |
| 检索维度不足 | 需按适用章节、标签、使用方式筛选写作指导 |

### 1.2 产品定位

**撰写技巧**（亦称「写作蓝图」）是从标书知识块中提炼的可长期复用的写作方法论资产。关注：

- 应该写什么
- 应该怎么写
- 应该如何组织内容
- 哪些内容必须覆盖
- 哪些地方容易遗漏

**不是**对知识块具体项目内容的摘要。

与**目录蓝图**互补：

| 模块 | 来源 | 结构 | 核心用途 |
|------|------|------|----------|
| 目录蓝图 | 文档目录子树 | 树形节点 | 章节目录怎么组织 |
| 撰写技巧 | 知识块内容 | 扁平字段 | 某一类章节该怎么写 |

### 1.3 建设目标

- 从知识浏览页一键 LLM 生成撰写技巧，自动落库为草稿
- 支持手动新建（可不绑定知识块，后续再关联）
- 独立列表/详情管理，顶栏导航可达
- 发布时预留 embedding 索引，供后续 AI 生成流水线检索（V1 不做列表语义搜索）

### 1.4 已锁定决策（brainstorming）

| 议题 | 决议 |
|------|------|
| 架构方案 | 独立表 `writing_techniques` + embedding 侧车（方案 A） |
| 知识块关系 | 严格 1:1（`source_chunk_id` 非空时）；`UNIQUE(kb_id, source_chunk_id)` |
| 手动创建 | 支持；`source_chunk_id` 可空，后续 `bind-source` |
| 页面范围 | 顶栏「撰写技巧」+ 列表 + 详情；知识浏览加「生成」入口 |
| 检索 | V1 无列表语义搜索；发布时异步建 embedding，供生成流水线预留 |
| 生成保存 | LLM 结果自动落库 `draft`；详情页编辑后手动「发布」 |
| confidence | 0~100；低分仅 UI 警告标签，不拦截保存/发布 |
| 知识块 purge | 保留撰写技巧；`source_chunk_id=NULL`，`source_invalid=true` |
| 已发布再生成 | 确认后覆盖全部 LLM 字段，`status` 回退 `draft`，需重新发布 |
| 主键类型 | UUID（与全库一致） |

### 1.5 不在范围（V1）

- 列表页语义搜索 UI 与 `/search` 端点
- 撰写技巧驱动标书生成（下游消费，后续 Epic）
- 知识块版本自动迁移（仅展示「来源版本可能已过期」轻提示）
- 多版本历史保留（覆盖即替换，仅 `version` 递增）

---

## 2. 方案对比

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A 独立表（采用）** | `writing_techniques` + embedding 侧车 | 边界清晰；支持无来源创建；与目录蓝图模式一致 | 多一套 CRUD |
| B JSONB 侧车 | 挂到 `knowledge_chunks` 列 | 实现快 | 无法脱离知识块；与可选关联冲突 |
| C 多态衍生表 | `knowledge_derivatives` | 长期可扩展 | V1 过度设计 |

---

## 3. 数据模型

### 3.1 主表 `writing_techniques`

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| `technique_id` | UUID PK | |
| `kb_id` | UUID NOT NULL | |
| `title` | varchar(100) NOT NULL | 标题，服务层 ≤30 字 |
| `applicable_scene` | text | 适用场景，≤100 字 |
| `writing_summary` | text | 写作简介，≤200 字 |
| `applicable_sections` | JSONB NOT NULL DEFAULT `[]` | 适用章节列表 |
| `tags` | JSONB NOT NULL DEFAULT `[]` | 检索标签，3~10 个（生成时建议，手动可放宽） |
| `usage_mode` | enum NOT NULL | `DIRECT` / `REFERENCE` / `EXTRACT` |
| `recommended_outline` | text | 推荐目录结构（Markdown 文本） |
| `writing_strategy` | text | 核心写作策略，≤200 字 |
| `must_include` | text | 必包含内容 |
| `notes` | text | 注意事项 |
| `output_requirement` | text | 输出要求 |
| `checklist` | text | 检查清单 |
| `confidence` | smallint NOT NULL DEFAULT 0 | 0~100，LLM `score` 映射 |
| `source_chunk_id` | bigint NULL | FK → `knowledge_chunks.id`，可空 |
| `source_invalid` | boolean NOT NULL DEFAULT false | 来源知识块已删除 |
| `status` | enum NOT NULL | `draft` / `published` |
| `version` | int NOT NULL DEFAULT 1 | 覆盖生成或发布时 +1 |
| `created_at` | timestamptz NOT NULL | |
| `updated_at` | timestamptz NOT NULL | |

**索引与约束**

```sql
CREATE UNIQUE INDEX uq_writing_techniques_kb_source_chunk
  ON writing_techniques (kb_id, source_chunk_id)
  WHERE source_chunk_id IS NOT NULL;

CREATE INDEX ix_writing_techniques_kb_id ON writing_techniques (kb_id);
CREATE INDEX ix_writing_techniques_status ON writing_techniques (kb_id, status);
```

### 3.2 侧车表 `writing_technique_embeddings`（V1 预留）

对齐 `blueprint_embeddings`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `technique_id` | UUID PK FK CASCADE | |
| `kb_id` | UUID | |
| `search_text` | text | 发布时拼接检索文本 |
| `embedding` | vector(1024) / JSON | |
| `embedding_status` | varchar(20) | pending / ready / failed / skipped |
| `content_hash` | varchar(64) | |
| `indexed_at` | timestamptz | |

`search_text` 拼接：`title` + `applicable_scene` + `writing_summary` + `tags` + `writing_strategy` + `must_include`。

### 3.3 级联与生命周期

| 事件 | 行为 |
|------|------|
| 删除撰写技巧 | CASCADE 删除 embedding |
| purge 删除 knowledge_chunks | **不删**撰写技巧；批量 `source_chunk_id=NULL`, `source_invalid=true` |
| bind-source | 校验目标 chunk 未被其他技巧占用 |
| 知识块 `is_latest` 切换 | 不自动失效；详情页轻提示来源版本可能过期 |

---

## 4. API 契约

**前缀**：`/api/v1/kbs/{kb_id}/writing-techniques`  
**响应**：沿用 `success()` / `error()` envelope。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/generate` | 从知识块 LLM 生成并自动落库为 `draft` |
| POST | `/` | 手动新建（`source_chunk_id` 可空） |
| PUT | `/{technique_id}` | 全量更新可编辑字段 |
| PUT | `/{technique_id}/publish` | `draft` → `published`；触发 embedding 后台任务 |
| PUT | `/{technique_id}/bind-source` | 绑定知识块 |
| GET | `/` | 分页列表 + 筛选 |
| GET | `/by-source?chunk_id=` | 查询某知识块是否已有撰写技巧 |
| GET | `/{technique_id}` | 详情 |
| DELETE | `/{technique_id}` | 删除 |

### 4.1 列表筛选（V1）

- `keyword`：匹配 `title` / `writing_summary`
- `tags`、`applicable_sections`（数组包含）
- `usage_mode`、`status`
- `confidence_min`、`confidence_max`
- `source_invalid`（bool）
- `has_source`（bool）

列表项额外返回 `embedding_status`（只读展示），不提供语义搜索。

### 4.2 Generate

**请求**

```json
{
  "chunk_id": 123,
  "confirm_overwrite": false
}
```

**行为**

1. 加载 `is_latest=true` 的知识块 `title` + `content`
2. 若已存在绑定该 chunk 的撰写技巧且 `confirm_overwrite=false` → 409
3. 调用 LLM（用户提供的完整 Prompt）
4. 解析 JSON；`score` → `confidence`
5. 新建或覆盖记录：`status=draft`，`version+=1`，`source_chunk_id=chunk_id`，`source_invalid=false`

| 条件 | HTTP | code |
|------|------|------|
| 知识块不存在 | 404 | `chunk_not_found` |
| 已存在且未确认覆盖 | 409 | `technique_exists` |
| LLM 未配置 | 502 | `technique_generate_failed` |
| LLM 超时 | 504 | `technique_generate_timeout` |
| JSON 解析/校验失败 | 502 | `technique_generate_failed` |

### 4.3 Bind-source

**请求**：`{ "chunk_id": 123 }`

| 条件 | HTTP | code |
|------|------|------|
| 目标 chunk 已被其他技巧绑定 | 409 | `chunk_already_bound` |
| chunk 不存在 | 404 | `chunk_not_found` |

### 4.4 Purge 影响计数

`check_purge_impact` 新增 `writing_techniques_invalidated`（将解绑失效的记录数，非删除数）。

---

## 5. LLM 生成

### 5.1 配置

```text
WRITING_TECHNIQUE_GENERATE_MODEL=qwen-plus
WRITING_TECHNIQUE_GENERATE_TIMEOUT_SEC=30
```

### 5.2 输入

- 知识块 `title` + `content`（超长按 `truncate_for_llm` 截断）
- V1 不传 `catalog_path`、tags 等元数据

### 5.3 Prompt

采用 brainstorming 确认的完整提示词（角色：资深标书编写专家；提取原则 5 条；各字段提取要求；输出纯 JSON）。

**LLM 输出字段映射**

| LLM JSON | DB 字段 |
|----------|---------|
| `title` | `title` |
| `applicable_scene` | `applicable_scene` |
| `writing_summary` | `writing_summary` |
| `applicable_sections` | `applicable_sections` |
| `tags` | `tags` |
| `usage_mode` | `usage_mode` |
| `recommended_outline` | `recommended_outline` |
| `writing_strategy` | `writing_strategy` |
| `must_include` | `must_include` |
| `notes` | `notes` |
| `output_requirement` | `output_requirement` |
| `checklist` | `checklist` |
| `score` | `confidence` |

### 5.4 服务层容错

| 场景 | 处理 |
|------|------|
| 空字段 | 存 `""` 或 `[]` |
| 无效 `usage_mode` | fallback `REFERENCE` |
| `confidence` 超范围 | clamp 0~100 |
| 文本超长 | `writing_technique_field_utils` 按上限截断 |

---

## 6. 前端设计

### 6.1 路由与导航

| 路由 | 页面 |
|------|------|
| `/knowledge/writing-techniques` | 撰写技巧列表 |
| `/knowledge/writing-techniques/:id` | 详情/编辑 |

`AppShell` 在「目录蓝图」旁新增「撰写技巧」。

### 6.2 组件

```text
components/WritingTechnique/
├── WritingTechniqueForm.tsx
├── WritingTechniqueMetaSection.tsx
├── WritingTechniqueGuidanceSection.tsx
└── ConfidenceBadge.tsx

pages/Knowledge/
├── WritingTechniqueListPage.tsx
├── WritingTechniqueDetailPage.tsx
└── KnowledgeBrowsePage.tsx    # 操作列加「生成撰写技巧」

services/writingTechniques.ts
```

### 6.3 知识浏览页

- 操作列：「生成撰写技巧」/ 已有则「重新生成」
- 已有技巧：点击前 `GET /by-source`；存在则 Modal 确认覆盖
- 生成成功 → 跳转详情页

### 6.4 详情页

分区：基础信息 / 写作指导 / 输出与检查 / 来源知识块。

- `ConfidenceBadge`：90+ 绿 / 70+ 蓝 / 50+ 橙 / &lt;50 红
- `source_invalid` → Alert「来源已失效」
- 操作：保存 / 发布 / 绑定知识块 / 删除

### 6.5 列表页

列：标题、适用场景（截断）、标签、使用方式、confidence、状态、来源状态、更新时间。

筛选：关键词、标签、使用方式、状态、confidence 区间。「新建撰写技巧」→ 空白详情。

---

## 7. 后端模块

```text
backend/src/
├── models/writing_technique.py
├── models/writing_technique_embedding.py
├── services/knowledge/
│   ├── writing_technique_service.py
│   ├── writing_technique_generate_service.py
│   ├── writing_technique_field_utils.py
│   └── writing_technique_embedding_task.py
├── api/routes/writing_techniques.py
├── api/schemas/writing_techniques.py
└── alembic/versions/YYYYMMDD_writing_techniques.py
```

`file_import_purge_service.py`：chunk 删除前调用 `invalidate_writing_techniques_by_chunk_ids`。

`main.py`：注册 `writing_techniques` router。

---

## 8. 测试策略

### 8.1 单元测试

- `writing_technique_generate_service`：JSON 解析、fallback、clamp
- `writing_technique_service`：1:1 冲突、覆盖回退 draft、publish
- purge：`source_invalid` 且记录保留

### 8.2 契约测试

- `POST /generate` 新建草稿
- `POST /generate` + `confirm_overwrite` 覆盖已发布
- `PUT /bind-source` 409
- `GET /by-source`

### 8.3 前端（可选 V1）

- `ConfidenceBadge` 区间
- 知识浏览确认 Modal

---

## 9. 与 Constitution 对齐

| 原则 | 对齐方式 |
|------|----------|
| Human Confirmation Gate | 生成落草稿；发布需人工操作 |
| Knowledge Asset First | 独立可检索、可治理的写作方法论资产 |
| Chapter-First | `applicable_sections` 章节维度；可追溯 `source_chunk_id` |
| Retrieval Before Generation | V1 预留 embedding；列表结构化筛选先行 |
