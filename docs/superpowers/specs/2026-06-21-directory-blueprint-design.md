# Design: 目录蓝图（Directory Blueprint）

**Date**: 2026-06-21  
**Status**: Approved (brainstorming)  
**Related**: 用户 PRD V2.0 · `docs/superpowers/specs/2026-06-18-knowledge-v2-design.md` · `backend/src/services/knowledge/prefill_service.py`  
**Problem**: 从已解析文档章节结构中提取并 AI 归纳为通用大纲模板，携带写作智能字段，独立存储与管理，为后续标书生成与知识检索提供结构化锚点。

---

## 1. 背景与目标

### 1.1 痛点

| 痛点 | 说明 |
|------|------|
| 缺少标准目录 | 同类方案目录结构随意，质量参差不齐 |
| 经验无法沉淀 | 优秀标书的章节组织、写作逻辑无法复用 |
| AI 生成结构不稳定 | 直接让大模型生成标书，目录随机性大 |
| 知识检索无锚点 | 知识块检索缺少章节维度约束 |

### 1.2 产品定位

**目录蓝图**是从已解析文档章节结构中提取、经大模型归纳而成的通用大纲模板。携带写作策略、章节作用、写作提示、重要程度标记、关键词提示等「写作智能」信息，作为「招标分析」与「标书生成」之间的中间层。

### 1.3 建设目标

- 从文档目录树一键提取并 AI 归纳为通用大纲
- 自动生成章节级写作指导，支持人工编辑、补全和调优
- 蓝图独立存储与管理（与 `knowledge_chunks` 解耦）
- 为后续标书生成提供结构化目录、内容指导、精准知识检索三大支撑

### 1.4 已锁定决策（brainstorming）

| 议题 | 决议 |
|------|------|
| 方案类型 | 独立 `scenario_tags` 自由标签（多选 + 自定义），不复用 `template_type` |
| 来源绑定 | 严格 1:1：`UNIQUE(kb_id, source_node_id)`，再次提取/保存即更新 |
| 文档 purge | 级联删除 `source_doc_id` 匹配的全部蓝图及节点 |
| 录入页布局 | 保持三栏：目录树 \| 章节预览 \| 右 Tab（知识录入 \| 目录蓝图） |
| LLM 配置 | 独立 `blueprint_generate_model` / `blueprint_generate_timeout_sec`（默认 30s） |
| 节点重要程度 | 单字段 `importance_level: required \| recommended \| optional`（替代双 bool） |
| 切换节点 | 立即清空两 Tab 全部内容，无拦截弹窗 |
| V1 字段范围 | 线框图 + `description` / `applicable_project_type` / `version` / `node_code` 均纳入 UI |
| version / description / node_code | 自动生成初值，均可手动编辑 |
| 主键类型 | UUID（与全库一致，PRD bigint 不对齐） |

### 1.5 不在范围（V1）

- 拖拽排序（PRD 标注未来版本）
- 蓝图驱动标书生成（下游消费）
- 蓝图归档 UI / 版本历史对比
- 向量检索集成
- E2E 自动化测试

---

## 2. 方案对比与决议

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **① 独立蓝图模块（推荐）** | 新表 + 新 API + 共享 `BlueprintEditor`；generate 无状态不落库 | 与 PRD 及 constitution 一致；边界清晰 | 工作量中等 |
| ② 蓝图作为知识块扩展 | 在 `knowledge_chunks` 存 JSON 树 | 少两张表 | 与 PRD 冲突；树形 CRUD 别扭 |
| ③ 仅前端草稿 | generate 不落库，无列表页 | 实现快 | 无法管理与复用，不满足 PRD §7 |

**决议：方案 ①** — 独立存储 + 无状态 generate + 人工确认后 save（符合 Human Confirmation Gate）。

---

## 3. 架构与数据模型

### 3.1 总体架构

```text
Frontend                          Backend
┌─────────────────────┐          ┌──────────────────────────┐
│ KnowledgeEntryPage  │──┐       │ blueprints router        │
│ BlueprintListPage   │  ├─────▶│ blueprint_generate_service│──▶ LLM
│ BlueprintDetailPage │──┘       │ blueprint_service        │
│ BlueprintEditor     │          │ file_import_purge_service │
└─────────────────────┘          └───────────┬──────────────┘
                                             ▼
                                 knowledge_blueprints
                                 knowledge_blueprint_nodes
                                 document_tree_nodes
```

### 3.2 表：`knowledge_blueprints`

| 字段 | 类型 | 说明 |
|------|------|------|
| blueprint_id | UUID PK | |
| kb_id | UUID | 所属知识库 |
| name | varchar(200) | 蓝图名称，必填 |
| description | text | LLM 生成初值，可编辑 |
| source_doc_id | UUID | 来源文档 |
| source_node_id | UUID | 来源节点，**UNIQUE(kb_id, source_node_id)** |
| source_chapter_title | varchar(200) | 来源章节标题 |
| product_tags | JSON array | 产品标签 |
| industry_tags | JSON array | 行业标签 |
| scenario_tags | JSON array | 方案类型（自由标签） |
| overall_strategy | text | 整体写作策略 |
| applicable_project_type | JSON array | 适用项目类型细类 |
| template_style | varchar(50) | formal / technical / concise 等 |
| usual_page_range | varchar(50) | 如「5-8页」 |
| related_regulations | JSON array | 相关规范 |
| common_mistakes | text | 常见失分点 |
| status | varchar(20) | active / archived（V1 仅 active 参与录入检测） |
| version | int | 新建=1，更新默认 +1，可手动改 |
| created_at / updated_at | timestamptz | |

**索引**：`kb_id`

### 3.3 表：`knowledge_blueprint_nodes`

| 字段 | 类型 | 说明 |
|------|------|------|
| node_id | UUID PK | |
| blueprint_id | UUID FK | |
| parent_node_id | UUID NULL | 根为 NULL |
| node_code | varchar(50) | 如 1、1.1，自动编号，可编辑 |
| node_title | varchar(200) | |
| node_level | int | |
| node_order | int | 同级排序 |
| purpose | text | 章节作用 |
| writing_goal | text | 写作目标 |
| writing_hint | text | 写作提示 |
| importance_level | enum | required / recommended / optional |
| content_type | varchar(50) | text / table / list / image |
| keyword_hint | JSON array | 检索关键词 |
| created_at | timestamptz | |

**索引**：`blueprint_id`、`parent_node_id`

### 3.4 Purge 级联

在 `file_import_purge_service` 删除文档时，同事务内：

```text
DELETE nodes WHERE blueprint_id IN (SELECT blueprint_id FROM blueprints WHERE source_doc_id = :doc_id)
DELETE blueprints WHERE source_doc_id = :doc_id
```

### 3.5 LLM 配置

```text
BLUEPRINT_GENERATE_MODEL=qwen-plus
BLUEPRINT_GENERATE_TIMEOUT_SEC=30
```

Prompt 要求 LLM 返回 JSON（含 `outline_title`、`overall_strategy`、`nodes[]` 等）。服务层将 LLM 的 `required_flag`/`recommended_flag` 映射为 `importance_level` 后返回前端；持久化只存枚举。

---

## 4. API 契约

**前缀**：`/api/v1/kbs/{kb_id}/blueprints`  
**响应**：沿用 `success()` / `error()` envelope。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/blueprints/generate` | 调 LLM，**不落库**，返回完整草稿 |
| GET | `/blueprints/by-source?doc_id=&node_id=` | 查是否已有蓝图 |
| POST | `/blueprints` | 新建；source 已存在 → 409 |
| PUT | `/blueprints/{blueprint_id}` | 全量替换 nodes + 更新主表 |
| GET | `/blueprints` | 分页列表 + 筛选 |
| GET | `/blueprints/{blueprint_id}` | 详情（嵌套 nodes 树） |
| DELETE | `/blueprints/{blueprint_id}` | 级联删节点 |

**扩展**：`GET /knowledge-chunks/entry/documents/{doc_id}/tree` 每个节点增加 `has_blueprint: bool`。

### 4.1 Generate 校验与错误

| 条件 | HTTP | code |
|------|------|------|
| 文档未 parse 完成 | 400 | document_not_ready |
| 节点无子节点 | 400 | no_child_nodes |
| LLM 超时 (>30s) | 504 | blueprint_generate_timeout |
| JSON 解析/格式错误 | 502 | blueprint_generate_failed |

### 4.2 Save 校验

| 条件 | HTTP |
|------|------|
| name 为空 | 422 |
| 无一级节点 | 422 |
| 同 source POST 重复 | 409 → 前端改 PUT |

PUT 时 `version` 默认 `existing.version + 1`，请求体可覆盖。

---

## 5. 后端模块

```
backend/src/
├── models/knowledge_blueprint.py
├── models/knowledge_blueprint_node.py
├── services/knowledge/
│   ├── blueprint_generate_service.py
│   ├── blueprint_service.py
│   └── blueprint_tree_utils.py
├── api/routes/blueprints.py
├── api/schemas/blueprints.py
└── alembic/versions/YYYYMMDD_blueprints.py
```

**`blueprint_generate_service`**：递归子树 → 层级文本 → LLM → JSON 解析 → `node_code` 编号 → 返回草稿 DTO。

**`blueprint_service`**：CRUD、by-source 查询、`replace_nodes` 全量替换、`delete_by_doc_id` 供 purge。

**`blueprint_tree_utils`**：nested ↔ flat 转换；`node_code` 自动编号。

---

## 6. 前端设计

### 6.1 路由与导航

| 路由 | 页面 |
|------|------|
| `/knowledge/entry` | 录入页（改造，右 Tab） |
| `/knowledge/blueprints` | 蓝图列表 |
| `/knowledge/blueprints/:id` | 蓝图详情/编辑 |

`AppShell` 新增导航项「目录蓝图」。

### 6.2 组件

```
components/Blueprint/
├── BlueprintEditor.tsx           # 共享编辑器
├── BlueprintMetaForm.tsx
├── BlueprintOutlineTree.tsx
├── BlueprintNodeDetailPanel.tsx
└── BlueprintOutlineTreeReadonly.tsx
pages/Knowledge/
├── KnowledgeEntryPage.tsx        # Tab 集成
├── BlueprintListPage.tsx
└── BlueprintDetailPage.tsx
services/blueprints.ts
```

### 6.3 录入页交互

**左栏**

- 【提取目录蓝图】：`parse_status=completed` 时显示；叶子/未选 disabled + Toast
- 节点旁：`ingested` 绿标 + `has_blueprint` 标记

**右栏 Tab**

| 触发 | 行为 |
|------|------|
| 【提取目录蓝图】 | 已有蓝图 → Modal 确认；切 blueprint Tab；generate |
| 【添加到知识库】 | 切 entry Tab；现有 prefill |
| 手动切 Tab | 各自保留编辑态 |
| 节点/文档变化 | **立即清空** 两 Tab |

**BlueprintEditor 底部**：【重新生成】【保存为蓝图】

### 6.4 列表与详情

- 列表：keyword + product/industry/scenario tags 筛选；Table + 分页；删除 Popconfirm
- 详情：只读展示全部字段；树默认全展开；点击标题复制；编辑复用 `BlueprintEditor`
- `readOnly` KB：写操作 disabled

### 6.5 node_code 策略

树结构变更时自动重算 `node_code`；用户手动编辑过的节点打 `codeManuallyEdited` 标记，不被自动覆盖。

---

## 7. 边界与异常

| 场景 | 处理 |
|------|------|
| 文档未解析 | 隐藏提取按钮 |
| 叶子节点 | disabled + Toast |
| LLM 超时/失败 | Toast + 可重试 |
| 切换节点 | 立即清空，无拦截 |
| 重复提取 | Modal 确认 |
| 重复保存 | 409 → Modal 覆盖 → PUT |
| 重新生成 | Modal 确认丢弃 |
| 文档 purge | 级联删蓝图 |
| name/大纲为空 | 校验禁止保存 |

---

## 8. 测试策略

### 8.1 后端单元测试

- `blueprint_generate_service`：子树拼接、JSON 解析、importance 映射、超时/格式错误（mock LLM）
- `blueprint_tree_utils`：flat/nested、node_code 编号
- `blueprint_service`：CRUD、唯一约束、version +1、replace_nodes
- `file_import_purge_service`：purge 级联删蓝图

### 8.2 后端集成测试

- generate → create 全流程
- 409 重复 POST → PUT 覆盖
- list 筛选、DELETE 级联
- tree 接口 `has_blueprint`

### 8.3 手工 Smoke

1. 提取 → 编辑 → 保存 → 树图标  
2. 重复提取确认 → 覆盖  
3. Tab 切换状态保留；切换节点清空  
4. 列表筛选 → 详情 → 复制 → 编辑 → 保存  
5. purge 文档 → 蓝图消失  

---

## 9. 验收标准（PRD §10）

| # | 验收项 | 预期 |
|---|--------|------|
| 1 | 按钮启用/禁用 | 按规则启用、禁用、提示 |
| 2 | 蓝图生成 | 加载态 → 树 + 全部写作智能字段 |
| 3 | 大纲编辑 | 增删改节点，顺序正确 |
| 4 | 节点详情编辑 | purpose/hint/importance/keyword 等可改 |
| 5 | 蓝图保存 | 独立表落库，Toast，树图标 |
| 6 | 重复提取与更新 | 弹窗确认，更新最新 |
| 7 | 重新生成 | 确认后重调 LLM |
| 8 | Tab 切换 | 手动切换保留；节点变更清空 |
| 9 | 蓝图列表 | 独立菜单，搜索筛选分页 |
| 10 | 蓝图详情 | 树形渲染，展开/折叠，复制标题 |
| 11 | 数据独立性 | 与 knowledge_chunks 不耦合 |
| 12 | 超时与异常 | 友好提示，可重试 |
| 13 | 校验 | 名称/大纲为空禁止保存 |

---

## 10. 实施顺序

1. DB migration + models  
2. blueprint_service + tree utils（TDD）  
3. blueprint_generate_service（TDD, mock LLM）  
4. API routes + integration tests  
5. purge 级联 + tree has_blueprint  
6. frontend services + BlueprintEditor 组件族  
7. KnowledgeEntryPage Tab 集成  
8. BlueprintListPage + BlueprintDetailPage + 导航  
9. 手工 smoke  

---

## 11. Spec Self-Review

- [x] 无 TBD / TODO 占位  
- [x] 架构与 API、前端、测试一致  
- [x] 范围聚焦单迭代，拖拽/下游消费明确 Out of Scope  
- [x] brainstorming 决策均已写入 §1.4，与 PRD 差异在 §1.4 明示  
- [x] `status=archived` 字段保留但 V1 无归档 UI，行为已定义  
